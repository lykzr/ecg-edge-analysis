/* 动态W8A8，INT32累加；层间/残差/偏置/缩放为FP32。ARM和HLS共用此核。 */
#include <stdint.h>
#include <math.h>
#include "cnn_int8_weights.h"
static float q_relu(float v){return v>0?v:0;}
static float q_scale(const float*x,int n){
#pragma HLS INLINE off
    float maximum=0;
    for(int i=0;i<n;i++){
#pragma HLS PIPELINE II=1
        float v=fabsf(x[i]);if(v>maximum)maximum=v;
    }
    union {float f;uint32_t u;} v;v.f=maximum;
    int exponent=(int)((v.u>>23)&255)-127-6;
    if(exponent< -24)exponent=-24;
    v.u=(uint32_t)(exponent+127)<<23;
    float scale=v.f;
    if(maximum>127*scale)scale*=2;
    return scale;
}
static int8_t q_value(float x,float inverse){
    float v=x*inverse;int q=(int)(v>=0?v+.5f:v-.5f);
    return (int8_t)(q>127?127:q< -127?-127:q);
}
static void q_conv(float x[16][128],float y[16][128],int cin,int length,int kernel,int offset,int layer){
#pragma HLS INLINE off
    float maximums[16];
    for(int i=0;i<cin;i++)maximums[i]=q_scale(x[i],length);
    float scale=maximums[0];for(int i=1;i<cin;i++)if(maximums[i]>scale)scale=maximums[i];
    int8_t q[16][128];float inverse=1/scale;
    for(int i=0;i<cin;i++)for(int t=0;t<length;t++){
#pragma HLS PIPELINE II=1
        q[i][t]=q_value(x[i][t],inverse);
    }
    int32_t acc[8][128];
#pragma HLS ARRAY_PARTITION variable=acc complete dim=1
#pragma HLS BIND_STORAGE variable=acc type=ram_2p impl=lutram
    for(int group=0;group<2;group++){
        for(int t=0;t<length;t++){
#pragma HLS PIPELINE II=1
            for(int lane=0;lane<8;lane++){
#pragma HLS UNROLL
                acc[lane][t]=0;
            }
        }
        for(int i=0;i<cin;i++)for(int k=0;k<kernel;k++){
            int8_t w[8];
#pragma HLS ARRAY_PARTITION variable=w complete
            for(int lane=0;lane<8;lane++){
#pragma HLS UNROLL
                w[lane]=q_conv_weights[lane][offset+(group*cin+i)*kernel+k];
            }
            for(int t=0;t<length;t++){
#pragma HLS PIPELINE II=1
#pragma HLS DEPENDENCE variable=acc inter false
                int at=t+k-kernel/2;
                if(at>=0&&at<length)for(int lane=0;lane<8;lane++){
#pragma HLS UNROLL
                    acc[lane][t]+=(int32_t)q[i][at]*(int32_t)w[lane];
                }
            }
        }
        for(int index=0;index<length*8;index++){
#pragma HLS PIPELINE II=1
            int t=index/8,lane=index%8;
            int ch=group*8+lane;y[ch][t]=(float)acc[lane][t]*(scale*q_conv_scales[layer*16+ch]);
        }
    }
}
static void q_dense(const float*x,int in,float*y,int out,int offset,int channel,bool relu){
#pragma HLS INLINE off
#pragma HLS BIND_STORAGE variable=q_dense_weights type=rom_1p impl=lutram
#pragma HLS BIND_STORAGE variable=q_dense_scales type=rom_1p impl=lutram
#pragma HLS BIND_STORAGE variable=q_dense_bias type=rom_1p impl=lutram
    float scale=q_scale(x,in),inverse=1/scale;int8_t q[269];
    for(int i=0;i<in;i++){
#pragma HLS PIPELINE II=1
        q[i]=q_value(x[i],inverse);
    }
    for(int o=0;o<out;o++){
        int32_t acc=0;
        for(int i=0;i<in;i++){
#pragma HLS PIPELINE II=1
            acc+=(int32_t)q[i]*(int32_t)q_dense_weights[offset+o*in+i];
        }
        float v=(float)acc*(scale*q_dense_scales[channel+o])+q_dense_bias[channel+o];
        y[o]=relu?q_relu(v):v;
    }
}
static void cnn_int8_core(const float input[261],float output[4]){
#pragma HLS ARRAY_PARTITION variable=q_conv_weights complete dim=1
#pragma HLS ALLOCATION instances=q_conv limit=1 function
#pragma HLS ALLOCATION instances=q_dense limit=1 function
#pragma HLS BIND_STORAGE variable=q_conv_scales type=rom_1p impl=lutram
#pragma HLS BIND_STORAGE variable=q_dense_scales type=rom_1p impl=lutram
#pragma HLS BIND_STORAGE variable=q_dense_bias type=rom_1p impl=lutram
    float a[16][128],b[16][128],c[16][128],x[16][128],features[269],r[3],hidden[64];
    for(int t=0;t<128;t++){x[0][t]=input[t];x[1][t]=t?input[t]-input[t-1]:0;}
    q_conv(x,a,2,128,7,0,0);
    for(int ch=0;ch<16;ch++)for(int t=0;t<128;t++)a[ch][t]=q_relu(a[ch][t]);
    int length=128,offset=28,layer=1;
    for(int block=0;block<3;block++){
        q_conv(a,b,16,length,5,offset,layer++);offset+=160;
        for(int ch=0;ch<16;ch++)for(int t=0;t<length;t++)b[ch][t]=q_relu(b[ch][t]);
        q_conv(b,c,16,length,5,offset,layer++);offset+=160;
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
    q_dense(features,269,hidden,64,24,8,true);q_dense(hidden,64,output,4,17240,72,false);
}
