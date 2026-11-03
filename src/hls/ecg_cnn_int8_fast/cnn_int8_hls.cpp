#include "int8_fast_core.h"
extern "C" void cnn_int8_hls(float input[261],float output[4]) {
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS INTERFACE s_axilite port=input bundle=control
#pragma HLS INTERFACE s_axilite port=output bundle=control
    cnn_int8_fast_core(input,output);
}
