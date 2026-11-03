/* 只加速head.0；复用原INT8卷积/量化/小全连接。原ARM与原PL源码保持不变。 */
#ifndef ECG_INT8_FAST_BASE_INCLUDED
#include "../ecg_cnn_int8/int8_core.h"
#endif
#ifndef ECG_INT8_CONV
#define ECG_INT8_CONV q_conv
#endif
#include "cnn_int8_fast_weights.h"

static void q_dense_head_fast(const float x[269], float y[64]) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=q_head_weights_fast complete dim=1
#pragma HLS ARRAY_PARTITION variable=q_head_scales_fast complete dim=1
#pragma HLS ARRAY_PARTITION variable=q_head_bias_fast complete dim=1
#pragma HLS BIND_STORAGE variable=q_head_weights_fast type=rom_1p impl=lutram
#pragma HLS BIND_STORAGE variable=q_head_scales_fast type=rom_1p impl=lutram
#pragma HLS BIND_STORAGE variable=q_head_bias_fast type=rom_1p impl=lutram
    float scale=q_scale(x,269),inverse=1/scale;
    int8_t q[269];
    for(int i=0;i<269;i++) {
#pragma HLS PIPELINE II=1
        q[i]=q_value(x[i],inverse);
    }
    for(int group=0;group<16;group++) {
        int32_t acc[4]={0,0,0,0};
#pragma HLS ARRAY_PARTITION variable=acc complete
        for(int i=0;i<269;i++) {
#pragma HLS PIPELINE II=1
            for(int lane=0;lane<4;lane++) {
#pragma HLS UNROLL
                acc[lane]+=(int32_t)q[i]*(int32_t)q_head_weights_fast[lane][group*269+i];
            }
        }
        for(int lane=0;lane<4;lane++) {
#pragma HLS PIPELINE II=1
            float v=(float)acc[lane]*(scale*q_head_scales_fast[lane][group])+q_head_bias_fast[lane][group];
            y[group*4+lane]=q_relu(v);
        }
    }
}

static void cnn_int8_fast_core(const float input[261],float output[4]) {
#pragma HLS ARRAY_PARTITION variable=q_conv_weights complete dim=1
#pragma HLS ALLOCATION instances=q_conv limit=1 function
#pragma HLS ALLOCATION instances=q_dense limit=1 function
#pragma HLS BIND_STORAGE variable=q_conv_scales type=rom_1p impl=lutram
#pragma HLS BIND_STORAGE variable=q_dense_scales type=rom_1p impl=lutram
#pragma HLS BIND_STORAGE variable=q_dense_bias type=rom_1p impl=lutram
    float a[16][128],b[16][128],c[16][128],x[16][128],features[269],r[3],hidden[64];
    for(int t=0;t<128;t++){x[0][t]=input[t];x[1][t]=t?input[t]-input[t-1]:0;}
    ECG_INT8_CONV(x,a,2,128,7,0,0);
    for(int ch=0;ch<16;ch++)for(int t=0;t<128;t++)a[ch][t]=q_relu(a[ch][t]);
    int length=128,offset=28,layer=1;
    for(int block=0;block<3;block++){
        ECG_INT8_CONV(a,b,16,length,5,offset,layer++);offset+=160;
        for(int ch=0;ch<16;ch++)for(int t=0;t<length;t++)b[ch][t]=q_relu(b[ch][t]);
        ECG_INT8_CONV(b,c,16,length,5,offset,layer++);offset+=160;
        for(int ch=0;ch<16;ch++)for(int t=0;t<length/2;t++){
            float v0=q_relu(a[ch][2*t]+c[ch][2*t]),v1=q_relu(a[ch][2*t+1]+c[ch][2*t+1]);b[ch][t]=v0>v1?v0:v1;
        }
        length/=2;
        for(int ch=0;ch<16;ch++)for(int t=0;t<length;t++)a[ch][t]=b[ch][t];
    }
    for(int ch=0;ch<16;ch++)for(int t=0;t<8;t++)features[ch*8+t]=a[ch][2*t]>a[ch][2*t+1]?a[ch][2*t]:a[ch][2*t+1];
    for(int i=0;i<3;i++){float v=(input[128+i]-q_rr_mean[i])/q_rr_std[i];r[i]=v< -5?-5:v>5?5:v;}
    q_dense(r,3,features+128,8,0,0,true);
    for(int i=0;i<3;i++)features[136+i]=r[i];
    for(int i=0;i<122;i++)features[139+i]=input[131+i];
    for(int i=0;i<8;i++)features[261+i]=input[253+i];
    q_dense_head_fast(features,hidden);
    q_dense(hidden,64,output,4,17240,72,false);
}
