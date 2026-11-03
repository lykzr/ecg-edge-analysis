/* 16个输出通道并行；每通道输入/卷积核累加顺序不变。 */
#include "cnn_int8_conv16_weights.h"
static void q_conv16(float x[16][128],float y[16][128],int cin,int length,int kernel,int offset,int layer) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=q_conv16_weights complete dim=1
#pragma HLS BIND_STORAGE variable=q_conv16_weights type=rom_1p impl=lutram
    float maximums[16];
    for(int i=0;i<cin;i++)maximums[i]=q_scale(x[i],length);
    float scale=maximums[0];for(int i=1;i<cin;i++)if(maximums[i]>scale)scale=maximums[i];
    int8_t q[16][128];float inverse=1/scale;
    for(int i=0;i<cin;i++)for(int t=0;t<length;t++) {
#pragma HLS PIPELINE II=1
        q[i][t]=q_value(x[i][t],inverse);
    }
    int32_t acc[16][128];
#pragma HLS ARRAY_PARTITION variable=acc complete dim=1
#pragma HLS BIND_STORAGE variable=acc type=ram_2p impl=lutram
    for(int t=0;t<length;t++) {
#pragma HLS PIPELINE II=1
        for(int lane=0;lane<16;lane++) {
#pragma HLS UNROLL
            acc[lane][t]=0;
        }
    }
    for(int i=0;i<cin;i++)for(int k=0;k<kernel;k++) {
        int8_t w[16];
#pragma HLS ARRAY_PARTITION variable=w complete
        for(int lane=0;lane<16;lane++) {
#pragma HLS UNROLL
            w[lane]=q_conv16_weights[lane][offset/2+i*kernel+k];
        }
        for(int t=0;t<length;t++) {
#pragma HLS PIPELINE II=1
#pragma HLS DEPENDENCE variable=acc inter false
            int at=t+k-kernel/2;
            if(at>=0&&at<length)for(int lane=0;lane<16;lane++) {
#pragma HLS UNROLL
                acc[lane][t]+=(int32_t)q[i][at]*(int32_t)w[lane];
            }
        }
    }
    for(int index=0;index<length*16;index++) {
#pragma HLS PIPELINE II=1
        int t=index/16,ch=index%16;
        y[ch][t]=(float)acc[ch][t]*(scale*q_conv_scales[layer*16+ch]);
    }
}
