#include "bridge.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t crc32(const char *p, unsigned n)
{
    uint32_t crc = UINT32_MAX;
    for (unsigned i=0; i<n; ++i) {
        crc ^= (unsigned char)p[i];
        for (unsigned bit=0; bit<8; ++bit)
            crc = (crc >> 1) ^ ((crc & 1U) ? 0xEDB88320U : 0);
    }
    return crc ^ UINT32_MAX;
}
static int put(EcgBridge *s, const char *p)
{
    unsigned n=(unsigned)strlen(p);
    if (n>256 || n>sizeof(s->tx)-s->used) return 0;
    if (!s->used) s->last_tx=s->last;
    for (unsigned i=0;i<n;++i) s->tx[(s->head+s->used+i)%sizeof(s->tx)]=(unsigned char)p[i];
    s->used+=n;
    if (s->used>s->peak) s->peak=s->used;
    return 1;
}
static int ack(EcgBridge *s, const char *state, const char *reason)
{
    char body[144], line[160];
    snprintf(body,sizeof(body),"A,ECG-IN-1,%s,%" PRIu32 ",%s,%s",
             s->session[0]?s->session:"none",s->samples,state,reason);
    snprintf(line,sizeof(line),"%s*%08" PRIX32 "\n",body,crc32(body,(unsigned)strlen(body)));
    return put(s,line);
}
static void fail(EcgBridge *s, const char *reason)
{
    if (s->failed) return;
    s->failed=1; s->error=reason;
    (void)ack(s,"ERROR",reason);
}
static int num(const char *p, long min, long max, long *value)
{
    char *end, canonical[32];
    long n=strtol(p,&end,10);
    if (!*p || *end || n<min || n>max) return 0;
    snprintf(canonical,sizeof(canonical),"%ld",n);
    if (strcmp(canonical,p)) return 0;
    *value=n; return 1;
}
static int session_ok(const char *p)
{
    size_t n=strlen(p);
    if (!n || n>32) return 0;
    for (size_t i=0;i<n;++i) if (!((p[i]>='a'&&p[i]<='z')||(p[i]>='A'&&p[i]<='Z')||
        (p[i]>='0'&&p[i]<='9')||p[i]=='_'||p[i]=='-'||p[i]=='.')) return 0;
    return 1;
}
static int status(EcgBridge *s, uint64_t now)
{
    char line[160]; uint32_t drop=s->io.read_reg(s->io.ctx,0x20);
    snprintf(line,sizeof(line),"T,-1,-1,?,%s,500,%" PRIu32 ",-1,0,%" PRIu32 "\n",
             drop?"OVF":"NA",drop,(uint32_t)(now/1000));
    return put(s,line);
}
static void packet(EcgBridge *s, uint64_t now)
{
    char *star=strchr(s->line,'*'), *fields[40]; unsigned n=0;
    if (!star || strlen(star+1)!=8) {fail(s,"BAD_CRC");return;}
    uint32_t expected=0;
    for (unsigned i=1;i<=8;++i) {
        char c=star[i]; unsigned digit;
        if (c>='0'&&c<='9') digit=(unsigned)(c-'0');
        else if(c>='A'&&c<='F') digit=(unsigned)(c-'A'+10);
        else {fail(s,"BAD_CRC");return;}
        expected=(expected<<4)|digit;
    }
    if (crc32(s->line,(unsigned)(star-s->line))!=expected) {fail(s,"BAD_CRC");return;}
    *star=0; fields[n++]=s->line;
    for(char *p=s->line;*p;++p) if(*p==',') {
        *p=0; if(n==40) {fail(s,"BAD_FIELDS");return;} fields[n++]=p+1;
    }
    for(unsigned i=0;i<n;++i) if(!fields[i][0]) {fail(s,"BAD_FIELDS");return;}
    if (!strcmp(fields[0],"I")) {
        if(s->active || s->busy || n!=6 || strcmp(fields[1],"ECG-IN-1") ||
           !session_ok(fields[2]) || strcmp(fields[3],"500") || strcmp(fields[5],"-1") ||
           (strcmp(fields[4],"ADC")&&strcmp(fields[4],"REPLAY")&&strcmp(fields[4],"SYNTH"))) {
            fail(s,"BAD_INIT");return;
        }
        strcpy(s->session,fields[2]);strcpy(s->source,fields[4]);
        if(s->io.read_reg(s->io.ctx,0x24)!=500 || s->io.read_reg(s->io.ctx,0x28)!=120 ||
           s->io.read_reg(s->io.ctx,0x2c)!=200) {fail(s,"CONFIG_MISMATCH");return;}
        if(s->io.read_reg(s->io.ctx,4)||s->io.read_reg(s->io.ctx,0x1c)||
           s->io.read_reg(s->io.ctx,0x30)||s->io.read_reg(s->io.ctx,0x20)||
           s->io.read_reg(s->io.ctx,0x10)||s->io.read_reg(s->io.ctx,0x14)!=7168) {
            fail(s,"NEED_FRESH_PL");return;
        }
        s->active=1;s->periodic=now/1000000;
        char line[192];snprintf(line,sizeof(line),
            "H,ECG-UART-1,ps-bridge-1,%s,%s,QRS-ORIG-60,500,-1,0xD\n",s->session,s->source);
        if(!put(s,line)||!ack(s,"READY","NA")) fail(s,"TX_QUEUE_FULL");
    } else if(!s->active) fail(s,"NEED_INIT");
    else if(s->busy) fail(s,"INPUT_BUSY");
    else if(!strcmp(fields[0],"D")) {
        long seq,count;
        if(n<4 || !num(fields[1],0,1800000,&seq) || !num(fields[2],1,32,&count) ||
           n!=(unsigned)count+3 || (uint32_t)seq!=s->samples || (uint32_t)seq+count>1800000) {
            fail(s,"BAD_SEQUENCE");return;
        }
        for(long i=0;i<count;++i) {
            long value;if(!num(fields[i+3],-32768,32767,&value)) {fail(s,"BAD_SAMPLE");return;}
            s->data[i]=(int16_t)value;
        }
        s->count=(unsigned)count;s->cursor=0;s->busy=1;s->tail=0;
    } else if(!strcmp(fields[0],"F")) {
        long total;
        if(n!=2 || !num(fields[1],0,1800000,&total) || (uint32_t)total!=s->samples) {
            fail(s,"BAD_TOTAL");return;
        }
        char line[128];snprintf(line,sizeof(line),"L,I,END reason=completed samples=%" PRIu32
                               " events=%" PRIu32 "\n",s->samples,s->events);
        if(!status(s,now)||!put(s,line)||!ack(s,"DONE","NA")) fail(s,"TX_QUEUE_FULL");
        s->done=1;
    } else fail(s,"BAD_TYPE");
}
void ecg_bridge_init(EcgBridge *s, BridgeIo io)
{
    memset(s,0,sizeof(*s));s->io=io;
}
void ecg_bridge_feed(EcgBridge *s, unsigned char c, uint64_t now)
{
    if(s->failed) return;
    if(now<s->last) {fail(s,"CLOCK_REVERSED");return;}
    s->last=now;
    if(s->done) {fail(s,"AFTER_END");return;}
    s->last_rx=now;
    if(c=='\n') {s->line[s->len]=0;packet(s,now);s->len=0;}
    else if(c<32 || c>126) fail(s,"BAD_ASCII");
    else if(s->len>=255) fail(s,"LINE_TOO_LONG");
    else s->line[s->len++]=(char)c;
}
static void events(EcgBridge *s)
{
    for(unsigned i=0;i<8 && (s->io.read_reg(s->io.ctx,4)&1);++i) {
        uint32_t pos=s->io.read_reg(s->io.ctx,8),rr=s->io.read_reg(s->io.ctx,12);
        uint32_t seq=s->io.read_reg(s->io.ctx,24);char line[128],hr[32];
        if(rr) {uint64_t tenth=(300000ULL+rr/2)/rr;
            snprintf(hr,sizeof(hr),"%" PRIu64 ".%" PRIu64,tenth/10,tenth%10);}
        else strcpy(hr,"-1");
        snprintf(line,sizeof(line),"E,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%s,?,-1\n",seq,pos,rr,hr);
        if(!put(s,line)) {fail(s,"TX_QUEUE_FULL");return;}
        s->io.write_reg(s->io.ctx,4,1);++s->events;
    }
    if(s->io.read_reg(s->io.ctx,0x20)) fail(s,"FIFO_OVERFLOW");
}
int ecg_bridge_step(EcgBridge *s, uint64_t now)
{
    if(now<s->last) {fail(s,"CLOCK_REVERSED");return 1;}
    s->last=now;
    if(!s->failed && !s->done) {
        if(s->len && now-s->last_rx>=2000000) fail(s,"PARTIAL_TIMEOUT");
        else if(s->active && now-s->last_rx>=5000000) fail(s,"INPUT_TIMEOUT");
    }
    if(!s->failed && s->active && !s->done) {
        if(s->busy && s->cursor<s->count) {
            s->io.write_reg(s->io.ctx,0,(uint16_t)s->data[s->cursor++]);++s->samples;
            if(s->cursor==s->count) s->tail=now;
        }
        events(s);
        if(!s->failed && s->busy && s->cursor==s->count && now-s->tail>=1000) {
            uint32_t first=s->samples-s->count;
            for(unsigned j=0;j<s->count;j+=8) {
                char line[160];unsigned count=s->count-j;if(count>8)count=8;
                int size=snprintf(line,sizeof(line),"W,%" PRIu32 ",%u",first+j,count);
                for(unsigned k=0;k<count;++k) size+=snprintf(line+size,sizeof(line)-(unsigned)size,",%d,NA",(int)s->data[j+k]);
                snprintf(line+size,sizeof(line)-(unsigned)size,"\n");
                if(!put(s,line)) {fail(s,"TX_QUEUE_FULL");break;}
            }
            if(!s->failed && !ack(s,"ACCEPTED","NA")) fail(s,"TX_QUEUE_FULL");
            s->busy=0;
        }
        if(now/1000000>s->periodic && !s->failed) {
            s->periodic=now/1000000;
            if(!status(s,now))fail(s,"TX_QUEUE_FULL");
        }
    }
    for(unsigned i=0;i<32 && s->used && s->io.tx_ready(s->io.ctx);++i) {
        s->io.tx_byte(s->io.ctx,s->tx[s->head]);s->head=(s->head+1)%sizeof(s->tx);--s->used;s->last_tx=now;
    }
    if(s->used && now-s->last_tx>=2000000) {s->failed=1;s->error="UART_STALLED";return 1;}
    return (s->failed||s->done)&&!s->used;
}
