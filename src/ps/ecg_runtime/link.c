/* 独立360Hz软件运行时USB_UART；旧500Hz/AXI接收器不变。 */
#include "link.h"
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
static int put(RuntimeLink *s, const char *p)
{
    unsigned n=(unsigned)strlen(p);
    if (n>256 || n>sizeof(s->tx)-s->used) return 0;
    if (!s->used) s->last_tx=s->now;
    for (unsigned i=0;i<n;++i) s->tx[(s->head+s->used+i)%sizeof(s->tx)]=(unsigned char)p[i];
    s->used+=n;
    if (s->used>s->peak) s->peak=s->used;
    return 1;
}
static int ack(RuntimeLink *s, const char *state, const char *reason)
{
    char body[144], line[160];
    snprintf(body,sizeof(body),"A,ECG-IN-1,%s,%" PRIu32 ",%s,%s",
             s->session[0]?s->session:"none",s->samples,state,reason);
    snprintf(line,sizeof(line),"%s*%08" PRIX32 "\n",body,crc32(body,(unsigned)strlen(body)));
    return put(s,line);
}
static void fail(RuntimeLink *s, const char *reason)
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

static int status(RuntimeLink*s){char line[160];snprintf(line,sizeof(line),"T,-1,-1,?,NA,360,0,-1,0,%" PRIu32 "\n",(uint32_t)(s->now/1000));return put(s,line);}
static int outputs(RuntimeLink*s,EcgClassRequest*r,int n){
 if(n<0){fail(s,"RUNTIME_ERROR");return 0;}
 for(int i=0;i<n;++i){EcgClassRequest work;EcgClassResult result;char line[192],hr[32];
  if(ecg_class_submit(&s->classifier,&r[i],s->now/1000)||ecg_class_take(&s->classifier,&work,s->now/1000)!=1||ecg_class_complete(&s->classifier,1,work.beat_id,work.input_status?work.input_status:ECG_CLASS_NO_MODEL,-1,&result,s->now/1000)!=1){fail(s,"CLASS_INTERFACE");return 0;}
  if(work.rr_samples){uint64_t tenth=(216000ULL+work.rr_samples/2)/work.rr_samples;snprintf(hr,sizeof(hr),"%" PRIu64 ".%" PRIu64,tenth/10,tenth%10);}else strcpy(hr,"-1");
  snprintf(line,sizeof(line),"E,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%s,?,-1\n",work.beat_id,work.position,work.rr_samples,hr);
  if(!put(s,line)){fail(s,"TX_QUEUE_FULL");return 0;}++s->events;
  snprintf(line,sizeof(line),"L,I,CLASS evt=%" PRIu32 " state=%" PRIu32 " ready=%" PRIu32 "\n",work.beat_id,result.status,work.ready_at);
  if(!put(s,line)){fail(s,"TX_QUEUE_FULL");return 0;}
  if(s->trace&&work.input_status!=ECG_CLASS_WINDOW_INCOMPLETE){for(unsigned j=0;j<128;j+=8){int size=snprintf(line,sizeof(line),"L,I,WIN evt=%" PRIu32 " offset=%u",work.beat_id,j);
   for(unsigned k=0;k<8;++k){uint32_t bits;memcpy(&bits,&work.waveform[j+k],4);size+=snprintf(line+size,sizeof(line)-(unsigned)size," %08" PRIX32,bits);}snprintf(line+size,sizeof(line)-(unsigned)size,"\n");if(!put(s,line)){fail(s,"TX_QUEUE_FULL");return 0;}}}
 }return 1;
}
static void packet(RuntimeLink*s){char*star=strchr(s->line,'*'),*f[40];unsigned n=0;
 if(!star||strlen(star+1)!=8){fail(s,"BAD_CRC");return;}uint32_t expected=0;
 for(unsigned i=1;i<=8;++i){char c=star[i];if(!((c>='0'&&c<='9')||(c>='A'&&c<='F'))){fail(s,"BAD_CRC");return;}expected=(expected<<4)|(uint32_t)(c<='9'?c-'0':c-'A'+10);}
 if(crc32(s->line,(unsigned)(star-s->line))!=expected){fail(s,"BAD_CRC");return;}*star=0;f[n++]=s->line;
 for(char*p=s->line;*p;++p)if(*p==','){*p=0;if(n==40){fail(s,"BAD_FIELDS");return;}f[n++]=p+1;}
 for(unsigned i=0;i<n;++i)if(!*f[i]){fail(s,"BAD_FIELDS");return;}
 if(!strcmp(f[0],"I")){if(s->active||n!=6||strcmp(f[1],"ECG-IN-1")||!session_ok(f[2])||strcmp(f[3],"360")||strcmp(f[5],"4096")||(strcmp(f[4],"REPLAY")&&strcmp(f[4],"SYNTH"))){fail(s,"BAD_INIT");return;}
  strcpy(s->session,f[2]);strcpy(s->source,f[4]);s->active=1;char line[192];snprintf(line,sizeof(line),"H,ECG-UART-1,ps-runtime-1,%s,%s,QRS26-ARM,360,4096,0xD\n",s->session,s->source);
  if(!put(s,line)||!put(s,"L,W,NO_MODEL backend=none classifier_not_delivered\n")||!ack(s,"READY","NA"))fail(s,"TX_QUEUE_FULL");
 }else if(!s->active)fail(s,"NEED_INIT");
 else if(s->busy)fail(s,"INPUT_BUSY");
 else if(!strcmp(f[0],"D")){long seq,count;if(n<4||!num(f[1],0,1800000,&seq)||!num(f[2],1,32,&count)||n!=(unsigned)count+3||(uint32_t)seq!=s->samples||(uint32_t)seq+count>1800000){fail(s,"BAD_SEQUENCE");return;}
  for(long i=0;i<count;++i){long x;if(!num(f[i+3],-32768,32767,&x)){fail(s,"BAD_SAMPLE");return;}s->data[i]=(int16_t)x;}s->count=(unsigned)count;s->cursor=0;s->busy=1;
 }else if(!strcmp(f[0],"F")){long total;if(n!=2||!num(f[1],0,1800000,&total)||(uint32_t)total!=s->samples){fail(s,"BAD_TOTAL");return;}
  EcgClassRequest requests[32];if(!outputs(s,requests,ecg_pipeline_finish(s->pipeline,requests)))return;
  char line[128];snprintf(line,sizeof(line),"L,I,END reason=completed samples=%" PRIu32 " events=%" PRIu32 "\n",s->samples,s->events);
  if(!status(s)||!put(s,line)||!ack(s,"DONE","NA"))fail(s,"TX_QUEUE_FULL");s->done=1;
 }else fail(s,"BAD_TYPE");
}
void ecg_link_init(RuntimeLink*s,RuntimeIo io,EcgPipeline*p,unsigned trace){memset(s,0,sizeof(*s));s->io=io;s->pipeline=p;s->trace=trace;const float mean[3]={0},std[3]={1,1,1};const uint8_t sha[32]={0};
 if(ecg_pipeline_init(p,1,mean,std)||ecg_class_init(&s->classifier,1,sha,2000))fail(s,"INIT_FAILED");
 if(!s->failed)put(s,"H,ECG-UART-1,ps-runtime-ready,boot,UNKNOWN,QRS26-ARM,360,4096,0xD\n");}
void ecg_link_feed(RuntimeLink*s,unsigned char c,uint64_t now){if(s->failed)return;if(now<s->now){fail(s,"CLOCK_REVERSED");return;}s->now=now;s->last_rx=now;
 if(s->done){fail(s,"AFTER_END");return;}if(c=='\n'){s->line[s->len]=0;packet(s);s->len=0;}else if(c<32||c>126)fail(s,"BAD_ASCII");else if(s->len>=255)fail(s,"LINE_TOO_LONG");else s->line[s->len++]=(char)c;}
int ecg_link_step(RuntimeLink*s,uint64_t now){if(now<s->now){fail(s,"CLOCK_REVERSED");return 1;}s->now=now;
 if(!s->failed&&!s->done){if(s->len&&now-s->last_rx>=2000000)fail(s,"PARTIAL_TIMEOUT");else if(s->active&&now-s->last_rx>=5000000)fail(s,"INPUT_TIMEOUT");}
 if(!s->active&&!s->failed&&now/1000000>s->periodic){s->periodic=now/1000000;if(!put(s,"H,ECG-UART-1,ps-runtime-ready,boot,UNKNOWN,QRS26-ARM,360,4096,0xD\n"))fail(s,"TX_QUEUE_FULL");}
 if(s->active&&!s->failed&&!s->done){if(s->busy&&s->cursor<s->count){EcgClassRequest requests[32];int16_t x=s->data[s->cursor++];int count=ecg_pipeline_push(s->pipeline,x,s->samples++,requests);outputs(s,requests,count);}
  if(s->busy&&s->cursor==s->count&&!s->failed){uint32_t start=s->samples-s->count;
   for(unsigned j=0;j<s->count;j+=8){char line[160];unsigned n=s->count-j;if(n>8)n=8;int size=snprintf(line,sizeof(line),"W,%" PRIu32 ",%u",start+j,n);
    for(unsigned k=0;k<n;++k)size+=snprintf(line+size,sizeof(line)-(unsigned)size,",%d,NA",s->data[j+k]);snprintf(line+size,sizeof(line)-(unsigned)size,"\n");if(!put(s,line)){fail(s,"TX_QUEUE_FULL");break;}}
   if(!s->failed&&!ack(s,"ACCEPTED","NA"))fail(s,"TX_QUEUE_FULL");s->busy=0;}
  if(now/1000000>s->periodic&&!s->failed){s->periodic=now/1000000;if(!status(s))fail(s,"TX_QUEUE_FULL");}
 }
 for(unsigned i=0;i<32&&s->used&&s->io.ready(s->io.ctx);++i){s->io.byte(s->io.ctx,s->tx[s->head]);s->head=(s->head+1)%sizeof(s->tx);--s->used;s->last_tx=now;}
 if(s->used&&now-s->last_tx>=2000000){s->failed=1;s->error="UART_STALLED";return 1;}
 return (s->failed||s->done)&&!s->used;
}
