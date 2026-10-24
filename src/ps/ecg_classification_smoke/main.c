/* ARM实机接口自检：无CNN、无QRS/AXI访问；测试时钟是受控输入。 */
#include "classification.h"
#include "class_build.h"
#include "xparameters.h"
#include "xuartps.h"
#include "xuartps_hw.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static EcgClassState state;
static EcgClassRequest req,work;
static EcgClassResult out;
static const uint8_t identity[32]={1,2,3}; /* 仅测试身份，不是权重。 */
static unsigned failures;
volatile int ecg_class_interface_result=-99;
static int tx_ok=1;
static void text(const char *p) {
    while(*p) {
        unsigned spins=1000000U;
        while(XUartPs_IsTransmitFull(XPAR_XUARTPS_0_BASEADDR)&&--spins){}
        if(!spins){tx_ok=0;return;}
        XUartPs_WriteReg(XPAR_XUARTPS_0_BASEADDR,XUARTPS_FIFO_OFFSET,(unsigned char)*p++);
    }
}
static void check(int value,const char *name) {
    text(value?"PASS ":"FAIL ");text(name);text("\r\n");if(!value)++failures;
}
static void init(void) {
    ecg_class_init(&state,1,identity,10);
    memset(&req,0,sizeof(req));req.generation=1;req.beat_id=1;req.position=360;
    req.rr_samples=360;req.sampling_hz=360;req.ready_at=600;
    for(unsigned i=0;i<128;++i)req.waveform[i]=(float)i/128.f;
}
int main(void) {
    XUartPs uart;
#ifdef SDT
    XUartPs_Config *cfg=XUartPs_LookupConfig(XPAR_XUARTPS_0_BASEADDR);
#else
    XUartPs_Config *cfg=XUartPs_LookupConfig(XPAR_XUARTPS_0_DEVICE_ID);
#endif
    if(!cfg||XUartPs_CfgInitialize(&uart,cfg,cfg->BaseAddress)!=XST_SUCCESS){ecg_class_interface_result=-1;return 1;}
    XUartPsFormat fmt={115200U,XUARTPS_FORMAT_8_BITS,XUARTPS_FORMAT_NO_PARITY,XUARTPS_FORMAT_1_STOP_BIT};
    if(XUartPs_SetDataFormat(&uart,&fmt)!=XST_SUCCESS){ecg_class_interface_result=-2;return 1;}
    XUartPs_SetOperMode(&uart,XUARTPS_OPER_MODE_NORMAL);
    XUartPs_SetOptions(&uart,XUARTPS_OPTION_STOP_BREAK);XUartPs_SetInterruptMask(&uart,0U);
    u32 control=XUartPs_ReadReg(cfg->BaseAddress,XUARTPS_CR_OFFSET);
    control&=~(XUARTPS_CR_TX_DIS|XUARTPS_CR_RX_DIS);control|=XUARTPS_CR_TX_EN|XUARTPS_CR_RX_EN;
    XUartPs_WriteReg(cfg->BaseAddress,XUARTPS_CR_OFFSET,control);
    text("BEGIN ECG_CLASS_INTERFACE build=" ECG_CLASS_BUILD_ID "\r\n");
    text("SCOPE ARM_TENSOR_QUEUE_ONLY NO_QRS NO_CNN NO_FLASH\r\n");
    float input[3]={.25f,1.f,0.f},mean[3]={.2f,.2f,.25f},std[3]={.1f,.1f,.02f},rr[3];
    check(ecg_class_normalize_rr(input,mean,std,rr)==0&&fabsf(rr[0]-.5f)<1e-6f&&rr[1]==5.f&&rr[2]==-5.f,"RR_FLOAT32_CLIP");
    init();int ok=1;
    for(unsigned i=1;i<=4;++i){req.beat_id=i;ok&=ecg_class_submit(&state,&req,0)==0;}
    req.beat_id=5;ok&=ecg_class_submit(&state,&req,0)==ECG_CLASS_BUSY&&state.last_id==4;
    check(ok,"BOUNDED_QUEUE_BUSY");
    ok=ecg_class_take(&state,&work,1)==1&&work.beat_id==1&&work.waveform[127]==127.f/128.f;
    ok&=ecg_class_complete(&state,1,1,ECG_CLASS_OK,2,&out,2)==1&&out.class_id==2&&out.valid&&out.request.position==360;
    ok&=ecg_class_submit(&state,&req,3)==0;check(ok,"IDENTITY_COMPLETE");
    init();ecg_class_submit(&state,&req,0);ecg_class_take(&state,&work,0);
    ok=ecg_class_expire(&state,&out,10)==1&&out.status==ECG_CLASS_TIMEOUT&&!out.valid&&out.class_id==-1;
    ok&=ecg_class_complete(&state,1,1,0,0,&out,11)==ECG_CLASS_BAD;check(ok,"TIMEOUT_LATE_REJECT");
    init();req.rr_samples=0;req.input_status=ECG_CLASS_MISSING_RR;
    ecg_class_submit(&state,&req,0);ecg_class_take(&state,&work,0);
    ok=ecg_class_complete(&state,1,1,0,0,&out,1)==ECG_CLASS_BAD;
    ok&=ecg_class_complete(&state,1,1,ECG_CLASS_MISSING_RR,-1,&out,2)==1&&!out.valid;
    check(ok,"FIRST_RR_UNKNOWN");
    init();ecg_class_submit(&state,&req,0);ok=ecg_class_cancel(&state,&out,1)==1&&out.status==ECG_CLASS_CANCELLED;
    ecg_class_init(&state,2,identity,10);ok&=ecg_class_submit(&state,&req,2)==ECG_CLASS_BAD;check(ok,"RESET_STALE_REJECT");
    init();req.waveform[5]=NAN;ok=ecg_class_submit(&state,&req,0)==ECG_CLASS_BAD;
    req.waveform[5]=0;ok&=ecg_class_submit(&state,&req,0)==0&&ecg_class_submit(&state,&req,0)==ECG_CLASS_BAD;
    ok&=ecg_class_take(&state,&work,0)==1&&ecg_class_take(&state,&work,0)==0;check(ok,"INVALID_DUPLICATE_SINGLE_FLIGHT");
    char line[100];snprintf(line,sizeof(line),"%s ECG_CLASS_INTERFACE failures=%u build=%s\r\n",failures?"FAIL":"PASS",failures,ECG_CLASS_BUILD_ID);
    text(line);ecg_class_interface_result=failures||!tx_ok?-3:1;
    unsigned drain=1000000U;
    while(!XUartPs_IsTransmitFifoEmpty(XPAR_XUARTPS_0_BASEADDR)&&--drain){}
    if(!drain)ecg_class_interface_result=-4;
    return failures?1:0;
}
