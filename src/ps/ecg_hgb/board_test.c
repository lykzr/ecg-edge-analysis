/* 独立ARM数值验收程序；固定合成输入，不接采集、不改变正式串口协议。 */
#include "hgb.h"
#include "hgb_fixture.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xiltimer.h"
#include "xuartps.h"
#include <string.h>
#include <stdint.h>

/* 导出到DDR供JTAG读取；不得用主机参考覆盖这些缓冲区。 */
HgbResult hgb_board_results[HGB_TEST_RESULTS];
HgbRequest hgb_board_requests[146];
int16_t hgb_board_codes[2][30000];
/* magic,state,case_count,result_size,total,counts[7],phase/timing[21]。 */
volatile uint32_t hgb_board_status[33];
static union {double align;unsigned char data[512*1024];} workspace;
static HgbRequest requests[480];

static uint32_t elapsed(XTime start){XTime end;XTime_GetTime(&end);return (uint32_t)((end-start)*1000000ULL/(uint64_t)(COUNTS_PER_SECOND));}
static int failed(int code){hgb_board_status[1]=(uint32_t)code;Xil_DCacheFlush();xil_printf("FAIL HGB_ARM code=%d\r\n",code);return 1;}
int main(void){
    _Static_assert(sizeof(HgbResult)==816,"结果布局不匹配");
    _Static_assert(sizeof(HgbRequest)==552,"请求布局不匹配");
    XUartPs uart;
    XUartPs_Config *config=XUartPs_LookupConfig(XPAR_XUARTPS_0_BASEADDR);
    if(!config||XUartPs_CfgInitialize(&uart,config,config->BaseAddress)!=XST_SUCCESS)return failed(-1);
    XUartPsFormat format={115200U,XUARTPS_FORMAT_8_BITS,XUARTPS_FORMAT_NO_PARITY,XUARTPS_FORMAT_1_STOP_BIT};
    if(XUartPs_SetDataFormat(&uart,&format)!=XST_SUCCESS)return failed(-2);
    /* 沿用已验全局计时器，仅使能计数，不改时钟或分频。 */
    uint32_t control=Xil_In32(0xF8F00208U);
    if(control&0xFF00U)return failed(-3);
    Xil_Out32(0xF8F00208U,control|1U);
    memset((void*)hgb_board_status,0,sizeof(hgb_board_status));
    hgb_board_status[0]=0x48474231;hgb_board_status[2]=7;
    hgb_board_status[3]=sizeof(HgbResult);hgb_board_status[4]=HGB_TEST_RESULTS;
    xil_printf("BEGIN HGB_ARM model=%s\r\n",hgb_model_sha256);
    unsigned offset=0;
    for(unsigned i=0;i<7;i++){
        XTime start;const HgbRequest *input=hgb_fixtures[i];uint32_t count=hgb_counts[i];
        hgb_board_status[1]=10+i;hgb_board_status[5+i]=count;Xil_DCacheFlush();
        if(i<2){
            HgbInput state={0};XTime_GetTime(&start);
            for(unsigned j=0;j<30000;j+=137){
                unsigned n=30000-j<137?30000-j:137;
                if(ecg_hgb_input(&state,hgb_signal+j,n,i==0,hgb_board_codes[i]+j))return failed(-10-(int)i);
            }
            hgb_board_status[12+i]=elapsed(start);
            size_t need=ecg_hgb_workspace_size(30000);if(need>sizeof(workspace.data))return failed(-20);
            XTime_GetTime(&start);
            if(ecg_hgb_prepare(hgb_board_codes[i],30000,requests,480,workspace.data,sizeof(workspace.data),&count))return failed(-30-(int)i);
            hgb_board_status[14+i]=elapsed(start);
            if(count!=hgb_counts[i])return failed(-40-(int)i);
            memcpy(hgb_board_requests+73*i,requests,count*sizeof(*requests));input=requests;
        }
        XTime_GetTime(&start);
        if(ecg_hgb_record(input,count,hgb_samples[i],hgb_board_results+offset))return failed(-50-(int)i);
        hgb_board_status[16+i]=elapsed(start);offset+=count;
        xil_printf("CASE HGB_ARM id=%d count=%d\r\n",i,count);
    }
    Xil_DCacheFlush();hgb_board_status[1]=1;Xil_DCacheFlush();
    xil_printf("DONE HGB_ARM cases=7 events=%d\r\n",offset);
    for(;;){__asm__ volatile("wfi");}
}
