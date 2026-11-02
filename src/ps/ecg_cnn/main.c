/* CNN-BATCH-1独立整段推理应用。只接已明确单位/采样率的mV，不接厂商34字节。 */
#include "hgb.h"
#include "cnn.h"
#include "stream.h"
#include "xil_cache.h"
#include "legacy.h"
#include "xiltimer.h"
#include "xuartps.h"
#include "xuartps_hw.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <stdarg.h>
#include <limits.h>

#define LIMIT 30000U
#define EVENTS 480U
static int16_t codes[LIMIT];
static HgbRequest requests[EVENTS];
static CnnResult results[EVENTS];
static union {double align;unsigned char data[512*1024];} workspace;
static uint32_t uart_base;
static uint64_t frequency;
#ifdef ECG_DUAL_MODEL
void hgb_batch_init(uint32_t,uint64_t);
int hgb_batch_session(char *v[8],unsigned n);
#endif
#ifdef ECG_CNN_PL
extern uint64_t cnn_arm_ticks,cnn_pl_call_ticks,cnn_pl_core_ticks;
extern uint32_t cnn_pl_beats,cnn_pl_mismatches;
void cnn_pl_clear(void);
#define CNN_IDENTITY "CNN-PL-1"
#else
#define CNN_IDENTITY "CNN-BATCH-1"
#endif
static XTime now(void){XTime t;XTime_GetTime(&t);return t;}
static uint32_t micros(XTime t){return (uint32_t)((now()-t)*1000000ULL/frequency);}
static int tx(const char *fmt,...){
    char line[256];va_list args;va_start(args,fmt);int n=vsnprintf(line,sizeof(line),fmt,args);va_end(args);
    if(n<0||(size_t)n>=sizeof(line))return -1;
    XTime start=now();
    for(int i=0;i<n;i++){
        while(XUartPs_IsTransmitFull(uart_base))if(micros(start)>4000000)return -1;
        XUartPs_WriteReg(uart_base,XUARTPS_FIFO_OFFSET,(unsigned char)line[i]);
    }
    return 0;
}
static int rx(unsigned char *out,unsigned n,uint32_t timeout){
    XTime start=now();unsigned used=0;
    while(used<n){
        uint32_t error=XUartPs_ReadReg(uart_base,XUARTPS_ISR_OFFSET)&(XUARTPS_IXR_OVER|XUARTPS_IXR_PARITY|XUARTPS_IXR_FRAMING);
        if(error){XUartPs_WriteReg(uart_base,XUARTPS_ISR_OFFSET,error);return -2;}
        if(!XUartPs_IsReceiveData(uart_base)){if(micros(start)>timeout)return -1;continue;}
        out[used++]=(unsigned char)XUartPs_ReadReg(uart_base,XUARTPS_FIFO_OFFSET);
    }
    return 0;
}
static int line(char out[192],uint32_t timeout){
    unsigned n=0;XTime start=now();
    while(n<191){
        unsigned char c;uint32_t spent=micros(start);if(spent>=timeout)return -1;
        if(rx(&c,1,timeout-spent))return -1;
        if(c=='\n'){out[n]=0;return 0;}
        if(c<' '||c>126)return -2;
        out[n++]=(char)c;
    }
    return -2;
}
static unsigned fields(char *s,char *out[8]){
    unsigned n=0;if(!*s||s[0]==','||s[strlen(s)-1]==','||strstr(s,",,"))return 0;
    char *p=strtok(s,",");while(p&&n<8){out[n++]=p;p=strtok(NULL,",");}return p?0:n;
}
static int number(const char *s,unsigned base,uint32_t *out){
    if(!*s)return -1;
    for(const char*p=s;*p;p++)if(!((*p>='0'&&*p<='9')||(base==16&&((*p>='a'&&*p<='f')||(*p>='A'&&*p<='F')))))return -1;
    char*end;errno=0;unsigned long value=strtoul(s,&end,base);if(errno||*end||value>UINT32_MAX)return -1;*out=(uint32_t)value;return 0;
}
static uint32_t crc32(const unsigned char *p,unsigned n){
    uint32_t crc=~0U;for(unsigned i=0;i<n;i++){crc^=p[i];for(unsigned j=0;j<8;j++)crc=(crc>>1)^((crc&1)?0xedb88320U:0U);}return ~crc;
}
static void model_ready(void){tx("H,%s,READY,500,mV,%s\n",CNN_IDENTITY,"16d56a6b1065df35f3e11c4cc285055b421978bd451d5da1b72df8f1744fcfc7");}
static void ready(void){
#ifdef ECG_DUAL_MODEL
    tx("H,ECG-DUAL-STREAM-1,READY,500,mV,H27-FP32,HGB-Q40\n");
#else
    model_ready();
#endif
}
static uint64_t legacy_clock(void *ctx){(void)ctx;return now()*1000000ULL/frequency;}
static int legacy_receive(void *ctx,unsigned char *c){
    (void)ctx;
    if(XUartPs_ReadReg(uart_base,XUARTPS_ISR_OFFSET)&(XUARTPS_IXR_OVER|XUARTPS_IXR_PARITY|XUARTPS_IXR_FRAMING))return -1;
    if(!XUartPs_IsReceiveData(uart_base))return 0;
    *c=(unsigned char)XUartPs_ReadReg(uart_base,XUARTPS_FIFO_OFFSET);return 1;
}
static int legacy_ready(void *ctx){(void)ctx;return !XUartPs_IsTransmitFull(uart_base);}
static void legacy_send(void *ctx,unsigned char c){(void)ctx;XUartPs_WriteReg(uart_base,XUARTPS_FIFO_OFFSET,c);}
static int session(char *v[8],unsigned fields_count){
    uint32_t sid,total,fs;
    if(fields_count!=7||strcmp(v[0],"I")||strcmp(v[1],"CNN-BATCH-1")||number(v[2],10,&sid)||!sid||number(v[3],10,&fs)||fs!=500||strcmp(v[4],"mV")||(strcmp(v[5],"hp05")&&strcmp(v[5],"raw"))||number(v[6],10,&total)||!total||total>LIMIT){tx("F,0,BAD_HEADER\n");return -1;}
    int highpass=!strcmp(v[5],"hp05");HgbInput input={0};uint32_t index=0,input_us=0;
    model_ready();
    if(tx("A,%u,READY,32\n",sid))return -1;
    while(index<total){
        char text[192],*f[8];uint32_t got_sid,start,n,crc;
        if(line(text,10000000)){tx("F,%u,INPUT_TIMEOUT_OR_UART\n",sid);return -1;}
        unsigned nf=fields(text,f);
        if(nf==2&&!strcmp(f[0],"X")&&!number(f[1],10,&got_sid)&&got_sid==sid){tx("S,%u,CANCEL\n",sid);return 0;}
        if(nf!=5||strcmp(f[0],"B")||number(f[1],10,&got_sid)||got_sid!=sid||number(f[2],10,&start)||start!=index||number(f[3],10,&n)||!n||n>32||n>total-index||number(f[4],16,&crc)){tx("F,%u,BAD_BLOCK\n",sid);return -1;}
        union {double align;unsigned char bytes[256];} block;
        if(rx(block.bytes,n*8,10000000)){tx("F,%u,PARTIAL_TIMEOUT_OR_UART\n",sid);return -1;}
        if(crc32(block.bytes,n*8)!=crc){tx("F,%u,BAD_CRC\n",sid);return -1;}
        double mv[32];memcpy(mv,block.bytes,n*8);XTime begin=now();
        if(ecg_hgb_input(&input,mv,n,highpass,codes+index)){tx("F,%u,INVALID_MV\n",sid);return -1;}
        input_us+=micros(begin);index+=n;if(tx("A,%u,NEXT,%u\n",sid,index))return -1;
    }
    char text[192],*f[8];uint32_t got_sid,count;
    if(line(text,10000000)||fields(text,f)!=3||strcmp(f[0],"D")||number(f[1],10,&got_sid)||got_sid!=sid||number(f[2],10,&count)||count!=total){tx("F,%u,BAD_END\n",sid);return -1;}
    uint32_t events=0;XTime begin=now();
    size_t need=ecg_hgb_workspace_size(total);
    if(need>sizeof(workspace.data)||ecg_hgb_prepare(codes,total,requests,EVENTS,workspace.data,sizeof(workspace.data),&events)){tx("F,%u,PREPARE_CAPACITY_OR_CONTRACT\n",sid);return -1;}
    uint32_t prepare_us=micros(begin);begin=now();
#ifdef ECG_CNN_PL
    cnn_pl_clear();
#endif
    if(cnn_record(requests,events,results)){tx("F,%u,CLASSIFY\n",sid);return -1;}
    uint32_t classify_us=micros(begin);
#ifdef ECG_CNN_PL
    if(tx("P,%u,FP32,%u,%u,%llu,%llu,%llu,%llu,100000000\n",sid,cnn_pl_beats,cnn_pl_mismatches,
        (unsigned long long)cnn_arm_ticks,(unsigned long long)cnn_pl_call_ticks,(unsigned long long)cnn_pl_core_ticks,(unsigned long long)frequency))return -1;
#endif
    for(uint32_t i=0;i<events;i++){
        CnnResult*r=results+i;uint32_t p[4];memcpy(p,r->probability,sizeof(p));
        if(tx("R,%u,%u,%u,%u,%u,%d,%08x,%08x,%08x,%08x\n",sid,r->beat_id,r->position,r->ready_at,r->status,r->class_id,p[0],p[1],p[2],p[3]))return -1;
    }
    return tx("D,%u,%u,%u,%u,%u,%u,%u\n",sid,total,events,input.clipped,input_us,prepare_us,classify_us);
}
#include "stream_uart.h"
int main(void){
    Xil_ICacheEnable();Xil_DCacheEnable();
    XUartPs uart;XUartPs_Config*config=XUartPs_LookupConfig(XPAR_XUARTPS_0_BASEADDR);
    if(!config||XUartPs_CfgInitialize(&uart,config,config->BaseAddress)!=XST_SUCCESS)return 1;
    uart_base=config->BaseAddress;frequency=(uint64_t)(COUNTS_PER_SECOND);
#ifdef ECG_DUAL_MODEL
    hgb_batch_init(uart_base,frequency);
#endif
    XUartPsFormat fmt={115200U,XUARTPS_FORMAT_8_BITS,XUARTPS_FORMAT_NO_PARITY,XUARTPS_FORMAT_1_STOP_BIT};
    if(XUartPs_SetDataFormat(&uart,&fmt)!=XST_SUCCESS)return 2;
    uint32_t control=Xil_In32(0xF8F00208U);if(control&0xff00U)return 3;Xil_Out32(0xF8F00208U,control|1U);
    ready();
    for(;;){char text[192],*f[8];int rc=line(text,2000000);
        if(rc==-1){ready();continue;}
        if(rc){tx("F,0,BAD_LINE\n");continue;}
        if(!strncmp(text,"I,ECG-IN-1,",11)){
            if(hgb_legacy_run(text,NULL,legacy_clock,legacy_receive,legacy_ready,legacy_send))return 4;
            XTime start=now();while(!XUartPs_IsTransmitEmpty(&uart)||XUartPs_IsSending(&uart))if(micros(start)>4000000)return 5;
            /* 不紧跟DONE追加H，兼容原客户端的完整结束检查。 */
            continue;
        }
        unsigned nf=fields(text,f);
#ifdef ECG_CNN_PL
        if(nf>1&&!strcmp(f[1],"CNN-STREAM-1")){(void)stream_session(f,nf);continue;}
#endif
#ifdef ECG_DUAL_MODEL
        if(nf>1&&!strcmp(f[1],"HGB-BATCH-1")){(void)hgb_batch_session(f,nf);continue;}
#endif
        (void)session(f,nf);
    }
}
