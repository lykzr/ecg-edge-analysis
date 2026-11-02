#include "cnn.h"
#include "cnn_offsets.h"
#include <math.h>
#include <string.h>
#ifdef ECG_CNN_PL
#define cnn_forward cnn_arm_forward
#endif
static void conv(const float*x,unsigned cin,unsigned length,float*y,unsigned cout,unsigned kernel,unsigned offset){
    const float*w=cnn_weights+offset;unsigned pad=kernel/2;
    for(unsigned o=0;o<cout;o++)for(unsigned t=0;t<length;t++){
        float sum=0;
        for(unsigned i=0;i<cin;i++)for(unsigned k=0;k<kernel;k++){
            int at=(int)t+(int)k-(int)pad;
            if(at>=0 && (unsigned)at<length)sum+=x[i*length+at]*w[(o*cin+i)*kernel+k];
        }
        y[o*length+t]=sum;
    }
}
static void linear(const float*x,unsigned in,float*y,unsigned out,unsigned w,unsigned b,int relu){
    for(unsigned o=0;o<out;o++){
        float sum=cnn_weights[b+o];for(unsigned i=0;i<in;i++)sum+=x[i]*cnn_weights[w+o*in+i];
        y[o]=relu?fmaxf(sum,0):sum;
    }
}
int cnn_forward(const float x[128],const float rr[3],const float hand[122],const float history[8],float out[4]){
    if(!x||!rr||!hand||!history||!out)return -1;
    for(unsigned i=0;i<3;i++)if(!isfinite(rr[i]))return -1;
    for(unsigned i=0;i<122;i++)if(!isfinite(hand[i]))return -1;
    for(unsigned i=0;i<8;i++)if(!isfinite(history[i]))return -1;
    float a[16*128],b[16*128],c[16*128],input[2*128],features[269],r[3],hidden[64];
    for(unsigned i=0;i<128;i++){if(!isfinite(x[i]))return -1;input[i]=x[i];input[128+i]=i?x[i]-x[i-1]:0;}
    for(unsigned i=0;i<3;i++)r[i]=fmaxf(-5,fminf(5,(rr[i]-cnn_weights[W_RR_MEAN+i])/cnn_weights[W_RR_STD+i]));
    conv(input,2,128,a,16,7,W_WAVE_0_WEIGHT);
    for(unsigned i=0;i<16*128;i++)a[i]=fmaxf(a[i],0);
    const unsigned offsets[3][2]={{W_WAVE_3_BODY_0_WEIGHT,W_WAVE_3_BODY_3_WEIGHT},{W_WAVE_4_BODY_0_WEIGHT,W_WAVE_4_BODY_3_WEIGHT},{W_WAVE_5_BODY_0_WEIGHT,W_WAVE_5_BODY_3_WEIGHT}};
    unsigned length=128;
    for(unsigned block=0;block<3;block++){
        conv(a,16,length,b,16,5,offsets[block][0]);for(unsigned i=0;i<16*length;i++)b[i]=fmaxf(b[i],0);
        conv(b,16,length,c,16,5,offsets[block][1]);
        for(unsigned ch=0;ch<16;ch++)for(unsigned t=0;t<length/2;t++){
            float v0=fmaxf(a[ch*length+2*t]+c[ch*length+2*t],0),v1=fmaxf(a[ch*length+2*t+1]+c[ch*length+2*t+1],0);
            b[ch*(length/2)+t]=fmaxf(v0,v1);
        }
        length/=2;memcpy(a,b,16*length*sizeof(float));
    }
    // 16点到8点的AdaptiveMaxPool，整除情况下每2点最大值。
    for(unsigned ch=0;ch<16;ch++)for(unsigned t=0;t<8;t++)features[ch*8+t]=fmaxf(a[ch*16+2*t],a[ch*16+2*t+1]);
    linear(r,3,features+128,8,W_RR_0_WEIGHT,W_RR_0_BIAS,1);
    memcpy(features+136,r,3*sizeof(float));memcpy(features+139,hand,122*sizeof(float));memcpy(features+261,history,8*sizeof(float));
    for(unsigned i=0;i<269;i++)if(!isfinite(features[i]))return -1;
    linear(features,269,hidden,64,W_HEAD_0_WEIGHT,W_HEAD_0_BIAS,1);
    linear(hidden,64,out,4,W_HEAD_3_WEIGHT,W_HEAD_3_BIAS,0);
    for(unsigned i=0;i<4;i++)if(!isfinite(out[i]))return -2;
    return 0;
}
