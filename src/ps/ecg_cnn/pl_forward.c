/* 完整FP32网络ARM/PL对照；前后处理不计入网络加速比。 */
#include "cnn.h"
#include "xil_io.h"
#include "xiltimer.h"
#include <math.h>
#include <string.h>
#define CNN_BASE 0x43C20000U
uint64_t cnn_arm_ticks,cnn_pl_call_ticks,cnn_pl_core_ticks;
uint32_t cnn_pl_beats,cnn_pl_mismatches;
int32_t cnn_last_arm_class,cnn_last_pl_class;
int cnn_arm_forward(const float*,const float*,const float*,const float*,float*);
static XTime clock_now(void){XTime t;XTime_GetTime(&t);return t;}
void cnn_pl_clear(void){cnn_arm_ticks=cnn_pl_call_ticks=cnn_pl_core_ticks=0;cnn_pl_beats=cnn_pl_mismatches=0;}
int cnn_forward(const float x[128],const float rr[3],const float hand[122],const float history[8],float out[4]){
    float reference[4],input[261];uint32_t bits[261];
    if(!x||!rr||!hand||!history||!out)return -1;
    memcpy(input,x,128*4);memcpy(input+128,rr,3*4);memcpy(input+131,hand,122*4);memcpy(input+253,history,8*4);
    for(unsigned i=0;i<261;i++)if(!isfinite(input[i]))return -1;
    XTime a=clock_now();int rc=cnn_arm_forward(x,rr,hand,history,reference);XTime b=clock_now();
    if(rc)return rc;
    if(!(Xil_In32(CNN_BASE)&4U))return -3;
    memcpy(bits,input,sizeof(bits));
    for(unsigned i=0;i<261;i++)Xil_Out32(CNN_BASE+0x800+4*i,bits[i]);
    Xil_Out32(CNN_BASE,1);XTime start=clock_now();
    while(!(Xil_In32(CNN_BASE)&2U))if(clock_now()-start>COUNTS_PER_SECOND/2)return -3;
    XTime end=clock_now();uint32_t raw[4];
    for(unsigned i=0;i<4;i++)raw[i]=Xil_In32(CNN_BASE+0x10+4*i);
    memcpy(out,raw,sizeof(raw));XTime c=clock_now();
    cnn_arm_ticks+=b-a;cnn_pl_call_ticks+=c-b;cnn_pl_core_ticks+=end-start;cnn_pl_beats++;
    unsigned arm_class=0,pl_class=0;int mismatch=0;
    for(unsigned i=0;i<4;i++){
        if(!isfinite(out[i]) || fabsf(out[i]-reference[i])>2e-4f+2e-5f*fabsf(reference[i]))mismatch=1;
        if(reference[i]>reference[arm_class])arm_class=i;
        if(out[i]>out[pl_class])pl_class=i;
    }
    cnn_last_arm_class=(int32_t)arm_class;cnn_last_pl_class=(int32_t)pl_class;
    if(mismatch||arm_class!=pl_class){cnn_pl_mismatches++;return -4;}
    return 0;
}
