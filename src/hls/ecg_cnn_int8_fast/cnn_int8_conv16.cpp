// 包含原公用算术，再令候选数据通路使用16输出卷积。
#include "../ecg_cnn_int8/int8_core.h"
#include "int8_conv16.h"
#define ECG_INT8_FAST_BASE_INCLUDED
#define ECG_INT8_CONV q_conv16
#include "int8_fast_core.h"
extern "C" void cnn_int8_hls(float input[261],float output[4]) {
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS INTERFACE s_axilite port=input bundle=control
#pragma HLS INTERFACE s_axilite port=output bundle=control
    cnn_int8_fast_core(input,output);
}
