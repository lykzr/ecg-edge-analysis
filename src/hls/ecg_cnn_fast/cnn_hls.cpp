// H27 FP32候选：全连接4输出并行，各输出内部逐项FP32累加次序不变。
#include "cnn_hls_weights.h"
#include "cnn_dense_fast_weights.h"
static float relu(float x){return x>0?x:0;}
static void conv(float x[16][128],float y[16][128],int cin,int length,int kernel,int offset){
#pragma HLS INLINE off
    float acc[4][128];
#pragma HLS ARRAY_PARTITION variable=acc complete dim=1
    for(int group=0;group<4;group++){
        for(int t=0;t<length;t++){
#pragma HLS PIPELINE II=1
            for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
                acc[lane][t]=0;
            }
        }
        for(int i=0;i<cin;i++)for(int k=0;k<kernel;k++){
            float w[4];
#pragma HLS ARRAY_PARTITION variable=w complete
            for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
                w[lane]=conv_weights[lane][offset+(group*cin+i)*kernel+k];
            }
            for(int t=0;t<length;t++){
#pragma HLS PIPELINE II=1
#pragma HLS DEPENDENCE variable=acc inter false
                int at=t+k-kernel/2;
                if(at>=0 && at<length){
                    float v=x[i][at];
                    for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
                        // 禁止融合乘加；保持与ARM相同的逐次FP32舍入。
                        float product=v*w[lane];
#pragma HLS BIND_OP variable=product op=fmul impl=fulldsp
                        acc[lane][t]=acc[lane][t]+product;
                    }
                }
            }
        }
        for(int t=0;t<length;t++){
#pragma HLS PIPELINE II=1
            for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
                y[group*4+lane][t]=acc[lane][t];
            }
        }
    }
}
static void dense_rr(const float*x,float*y){
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=dense_rr_weights complete dim=1
#pragma HLS ARRAY_PARTITION variable=dense_rr_bias complete dim=1
    for(int group=0;group<2;group++){
        float sum[4];
#pragma HLS ARRAY_PARTITION variable=sum complete
        for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
            sum[lane]=dense_rr_bias[lane][group];
        }
        for(int i=0;i<3;i++){
#pragma HLS PIPELINE
            float v=x[i];
            for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
                float product=v*dense_rr_weights[lane][group*3+i];
#pragma HLS BIND_OP variable=product op=fmul impl=fulldsp
                sum[lane]=sum[lane]+product;
            }
        }
        for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
            y[group*4+lane]=relu(sum[lane]);
        }
    }
}
static void dense_head(const float*x,float*y){
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=dense_head_weights complete dim=1
#pragma HLS ARRAY_PARTITION variable=dense_head_bias complete dim=1
    for(int group=0;group<16;group++){
        float sum[4];
#pragma HLS ARRAY_PARTITION variable=sum complete
        for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
            sum[lane]=dense_head_bias[lane][group];
        }
        for(int i=0;i<269;i++){
#pragma HLS PIPELINE
            float v=x[i];
            for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
                float product=v*dense_head_weights[lane][group*269+i];
#pragma HLS BIND_OP variable=product op=fmul impl=fulldsp
                sum[lane]=sum[lane]+product;
            }
        }
        for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
            y[group*4+lane]=relu(sum[lane]);
        }
    }
}
static void dense_out(const float*x,float*y){
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=dense_out_weights complete dim=1
#pragma HLS ARRAY_PARTITION variable=dense_out_bias complete dim=1
    for(int group=0;group<1;group++){
        float sum[4];
#pragma HLS ARRAY_PARTITION variable=sum complete
        for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
            sum[lane]=dense_out_bias[lane][group];
        }
        for(int i=0;i<64;i++){
#pragma HLS PIPELINE
            float v=x[i];
            for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
                float product=v*dense_out_weights[lane][group*64+i];
#pragma HLS BIND_OP variable=product op=fmul impl=fulldsp
                sum[lane]=sum[lane]+product;
            }
        }
        for(int lane=0;lane<4;lane++){
#pragma HLS UNROLL
            y[group*4+lane]=sum[lane];
        }
    }
}
extern "C" void cnn_hls(float input[261],float output[4]){
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS INTERFACE s_axilite port=input bundle=control
#pragma HLS INTERFACE s_axilite port=output bundle=control
#pragma HLS ARRAY_PARTITION variable=conv_weights complete dim=1
    float a[16][128],b[16][128],c[16][128],x[16][128];
    float features[269],r[3],hidden[64];
    for(int t=0;t<128;t++){
#pragma HLS PIPELINE II=1
        x[0][t]=input[t];x[1][t]=t?input[t]-input[t-1]:0;
    }
    conv(x,a,2,128,7,0);
    for(int ch=0;ch<16;ch++)for(int t=0;t<128;t++){
#pragma HLS PIPELINE II=1
        a[ch][t]=relu(a[ch][t]);
    }
    int length=128,offset=56;
    for(int block=0;block<3;block++){
        conv(a,b,16,length,5,offset);offset+=320;
        for(int ch=0;ch<16;ch++)for(int t=0;t<length;t++){
#pragma HLS PIPELINE II=1
            b[ch][t]=relu(b[ch][t]);
        }
        conv(b,c,16,length,5,offset);offset+=320;
        for(int ch=0;ch<16;ch++)for(int t=0;t<length/2;t++){
#pragma HLS PIPELINE II=1
            float v0=relu(a[ch][2*t]+c[ch][2*t]),v1=relu(a[ch][2*t+1]+c[ch][2*t+1]);
            b[ch][t]=v0>v1?v0:v1;
        }
        length/=2;
        for(int ch=0;ch<16;ch++)for(int t=0;t<length;t++){
#pragma HLS PIPELINE II=1
            a[ch][t]=b[ch][t];
        }
    }
    for(int ch=0;ch<16;ch++)for(int t=0;t<8;t++){
#pragma HLS PIPELINE II=1
        features[ch*8+t]=a[ch][2*t]>a[ch][2*t+1]?a[ch][2*t]:a[ch][2*t+1];
    }
    for(int i=0;i<3;i++){
        float v=(input[128+i]-rr_mean[i])/rr_std[i];r[i]=v< -5?-5:v>5?5:v;
    }
    dense_rr(r,features+128);
    for(int i=0;i<3;i++)features[136+i]=r[i];
    for(int i=0;i<122;i++)features[139+i]=input[131+i];
    for(int i=0;i<8;i++)features[261+i]=input[253+i];
    dense_head(features,hidden);
    dense_out(hidden,output);
}
