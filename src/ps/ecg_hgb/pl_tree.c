/* 同一心拍在ARM和PL执行相同Q40树分数；输出PL分数的softmax。 */
#include "hgb.h"
#include "hgb_pl_fixture.h"
#include "xil_io.h"
#include "xiltimer.h"
#include <math.h>
#include <string.h>
#define BASE 0x43C10000U
uint64_t hgb_pl_arm_ticks,hgb_pl_call_ticks,hgb_pl_cycles;
uint32_t hgb_pl_beats,hgb_pl_mismatches;
void hgb_pl_clear(void){hgb_pl_arm_ticks=0;hgb_pl_call_ticks=0;hgb_pl_cycles=0;hgb_pl_beats=0;hgb_pl_mismatches=0;}
static uint32_t ordered(uint32_t u){if(!(u&0x7fffffffU))u=0;return u>>31?~u:u^0x80000000U;}
int ecg_hgb_probability(const float x[192],double p[3]){
    uint32_t bits[192];int64_t arm[3],pl[3];XTime a,b,c;
    for(unsigned i=0;i<192;i++)if(!isfinite(x[i]))return -1;
    if(Xil_In32(BASE)!=0x48474231 || Xil_In32(BASE+0x28)!=40)return -3;
    memcpy(bits,x,sizeof(bits));
    XTime_GetTime(&a);
    for(unsigned k=0;k<3;k++){
        arm[k]=hgb_qbaseline[k];
        for(unsigned t=0;t<64;t++){
            unsigned at=hgb_qroots[k][t];
            for(;;){const HgbQNode*n=&hgb_qnodes[k][at];
                if(n->leaf){arm[k]+=n->value;break;}
                at=ordered(bits[n->feature])<=n->threshold?n->left:n->right;
            }
        }
    }
    XTime_GetTime(&b);
    for(unsigned i=0;i<192;i++)Xil_Out32(BASE+0x100+4*i,bits[i]);
    Xil_Out32(BASE+4,1);
    unsigned status,limit=100000;
    do{status=Xil_In32(BASE+4);}while(!(status&2)&&--limit);
    if(!limit || status&4)return -3;
    for(unsigned k=0;k<3;k++){
        uint32_t lo=Xil_In32(BASE+0x10+k*8),hi=Xil_In32(BASE+0x14+k*8);
        pl[k]=(int64_t)(((uint64_t)hi<<32)|lo);
    }
    XTime_GetTime(&c);
    hgb_pl_arm_ticks+=b-a;hgb_pl_call_ticks+=c-b;hgb_pl_cycles+=Xil_In32(BASE+8);hgb_pl_beats++;
    for(unsigned k=0;k<3;k++)if(pl[k]!=arm[k]){hgb_pl_mismatches++;return -4;}
    for(unsigned k=0;k<3;k++)p[k]=(double)pl[k]/1099511627776.0;
    double max=p[0];for(unsigned k=1;k<3;k++)if(p[k]>max)max=p[k];
    double sum=0;for(unsigned k=0;k<3;k++){p[k]=exp(p[k]-max);sum+=p[k];}
    for(unsigned k=0;k<3;k++)p[k]/=sum;
    return 0;
}
