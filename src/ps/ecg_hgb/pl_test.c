/* 独立JTAG演示：同一组160个特征、同Q40精度、ARM与PL树分类比较。 */
#include "hgb_pl_fixture.h"
#include "xil_io.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include "xiltimer.h"
#include "xuartps.h"
#define BASE 0x43C10000U
/* JTAG可读取：magic,state,count,ARM总ticks,PL调用总ticks,PL总cycles,maxcycles。 */
volatile uint32_t hgb_pl_status[8];
static uint32_t ordered(uint32_t u){if(!(u&0x7fffffffU))u=0;return u>>31?~u:u^0x80000000U;}
static void reference(const uint32_t x[192],int64_t out[3]){
    for(unsigned c=0;c<3;c++){
        out[c]=hgb_qbaseline[c];
        for(unsigned t=0;t<64;t++){
            unsigned a=hgb_qroots[c][t];
            for(;;){
                const HgbQNode *n=&hgb_qnodes[c][a];
                if(n->leaf){out[c]+=n->value;break;}
                a=ordered(x[n->feature])<=n->threshold?n->left:n->right;
            }
        }
    }
}
static int fail(unsigned code){hgb_pl_status[1]=code;Xil_DCacheFlush();xil_printf("FAIL HGB_PL code=%d\r\n",code);return 1;}
int main(void){
    XUartPs uart;XUartPs_Config *cfg=XUartPs_LookupConfig(XPAR_XUARTPS_0_BASEADDR);
    if(!cfg||XUartPs_CfgInitialize(&uart,cfg,cfg->BaseAddress)!=XST_SUCCESS)return 1;
    XUartPs_SetBaudRate(&uart,115200);
    Xil_ICacheEnable();Xil_DCacheEnable();
    uint32_t ctl=Xil_In32(0xF8F00208U);if(ctl&0xff00U)return fail(1);Xil_Out32(0xF8F00208U,ctl|1);
    hgb_pl_status[0]=0x48475031;hgb_pl_status[1]=1;
    if(Xil_In32(BASE)!=0x48474231 || Xil_In32(BASE+0x28)!=40)return fail(2);
    xil_printf("BEGIN HGB_PL v92-fold0 Q40 ARM=Cortex-A9 PL=100MHz vectors=160\r\n");
    /* 首轮预热缓存；两轮保留完整数值核对，仅第二轮计入汇总。 */
    for(unsigned pass=0;pass<2;pass++)for(unsigned v=0;v<160;v++){
        int64_t arm[3],pl[3];XTime a,b,c;
        XTime_GetTime(&a);reference(hgb_test_features[v],arm);XTime_GetTime(&b);
        for(unsigned i=0;i<192;i++)Xil_Out32(BASE+0x100+4*i,hgb_test_features[v][i]);
        Xil_Out32(BASE+4,1);
        unsigned status=0,limit=100000;
        do{status=Xil_In32(BASE+4);}while(!(status&2) && --limit);
        if(!limit || (status&4))return fail(3);
        for(unsigned k=0;k<3;k++){
            uint32_t lo=Xil_In32(BASE+0x10+8*k),hi=Xil_In32(BASE+0x14+8*k);
            pl[k]=(int64_t)(((uint64_t)hi<<32)|lo);
        }
        XTime_GetTime(&c);
        for(unsigned k=0;k<3;k++)if(pl[k]!=arm[k] || arm[k]!=hgb_test_scores[v][k])return fail(10+v);
        uint32_t cycles=Xil_In32(BASE+8);
        if(pass){
            hgb_pl_status[2]++;hgb_pl_status[3]+=(uint32_t)(b-a);hgb_pl_status[4]+=(uint32_t)(c-b);
            hgb_pl_status[5]+=cycles;if(cycles>hgb_pl_status[6])hgb_pl_status[6]=cycles;
            xil_printf("BEAT,%d,ARM_ticks,%d,PL_call_ticks,%d,PL_cycles,%d\r\n",v,(uint32_t)(b-a),(uint32_t)(c-b),cycles);
        }
    }
    hgb_pl_status[7]=(uint32_t)COUNTS_PER_SECOND;hgb_pl_status[1]=2;Xil_DCacheFlush();
    xil_printf("PASS HGB_PL vectors=160 ARM_ticks=%d PL_call_ticks=%d PL_cycles=%d timer_hz=%d\r\n",hgb_pl_status[3],hgb_pl_status[4],hgb_pl_status[5],hgb_pl_status[7]);
    while(1){}
}
