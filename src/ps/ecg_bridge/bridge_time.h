/* 默认全局计时器tick转微秒；频率参数须已求值为正数，不在表达式内展开BSP宏。 */
#ifndef ECG_BRIDGE_TIME_H
#define ECG_BRIDGE_TIME_H
#include <stdint.h>
static inline uint64_t ecg_bridge_time_us(uint64_t ticks, uint64_t frequency)
{
    /* 先取商和余数，避免将长期累计tick直接乘1000000造成溢出。 */
    return (ticks / frequency) * UINT64_C(1000000)
         + (ticks % frequency) * UINT64_C(1000000) / frequency;
}
#endif
