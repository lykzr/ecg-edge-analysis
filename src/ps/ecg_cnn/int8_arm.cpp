#include <math.h>
#include "int8_core.h"
extern "C" int cnn_int8_arm_forward(const float *input,float *output){
    for(int i=0;i<261;i++)if(!isfinite(input[i]))return -1;
    cnn_int8_core(input,output);
    for(int i=0;i<4;i++)if(!isfinite(output[i]))return -2;
    return 0;
}
