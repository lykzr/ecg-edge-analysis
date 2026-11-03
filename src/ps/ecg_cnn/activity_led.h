/* 仅匹配含AXI GPIO工作灯的候选镜像；不进入CNN计时区间。 */
#ifndef ECG_ACTIVITY_LED_H
#define ECG_ACTIVITY_LED_H
#include "xil_io.h"
static void activity_set(int active){
    Xil_Out32(0x43C40000U,active?1U:0U);
}
static void activity_init(void){
    activity_set(0);
    Xil_Out32(0x43C40004U,0U);
}
#endif
