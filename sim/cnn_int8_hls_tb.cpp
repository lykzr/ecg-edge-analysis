#include <math.h>
#include <stdio.h>
#include "cnn_int8_vectors.h"
extern "C" void cnn_int8_hls(float input[261],float output[4]);
int main(){
    float maximum=0;
    for(int n=0;n<12;n++){
        float input[261],output[4];for(int i=0;i<261;i++)input[i]=q_inputs[n][i];
        cnn_int8_hls(input,output);
        for(int i=0;i<4;i++){
            float error=fabsf(output[i]-q_expected[n][i]);if(error>maximum)maximum=error;
            if(!isfinite(output[i])||error>1e-5f+1e-6f*fabsf(q_expected[n][i])){printf("FAIL %d %d %.9g %.9g\n",n,i,output[i],q_expected[n][i]);return 1;}
        }
    }
    printf("PASS INT8 12 vectors max_error %.9g\n",maximum);return 0;
}
