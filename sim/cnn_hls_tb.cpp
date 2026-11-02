// 固定容差和类别对照；不把黄金一致性称分类准确率。
#include <cmath>
#include <cstdio>
#include "cnn_hls_vectors.h"
extern "C" void cnn_hls(float input[261],float output[4]);
int main(){
    float max_error=0;
    for(int v=0;v<12;v++){
        float in[261],out[4];for(int i=0;i<261;i++)in[i]=inputs[v][i];
        cnn_hls(in,out);int a=0,b=0;
        for(int k=0;k<4;k++){
            float error=std::fabs(out[k]-expected[v][k]);if(error>max_error)max_error=error;
            if(!std::isfinite(out[k]) || error>2e-4f+2e-5f*std::fabs(expected[v][k]))return 1;
            if(out[k]>out[a])a=k;if(expected[v][k]>expected[v][b])b=k;
        }
        if(a!=b)return 2;
    }
    std::printf("PASS H27_HLS_GOLDEN 12 max_error=%.9g\n",max_error);return 0;
}
