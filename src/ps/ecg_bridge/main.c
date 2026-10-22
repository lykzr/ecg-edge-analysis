/* 领航者V2现有smoke硬件上的独立接收中转；不含AFE驱动或CNN。 */
#include "bridge.h"
#include "bridge_time.h"
#include "xil_io.h"
#include "xparameters.h"
#include "xiltimer.h"
#include "xuartps.h"
#include "xuartps_hw.h"
#include <inttypes.h>
#include <stdio.h>
#ifndef XTIMER_IS_DEFAULT_TIMER
#error "This candidate requires the Cortex-A9 default global timer BSP"
#endif
/* 当前BSP的xiltimer/core/default_timer/globaltimer_sleep_zynq.c定义。 */
#define ECG_GLOBAL_TIMER_BASE 0xF8F00200U
#define ECG_GLOBAL_TIMER_CONTROL 0x08U

static EcgBridge bridge;
/* 便于调试器读取；不使用printf与协议混写。0=运行，1=完成，负数=失败。 */
volatile int ecg_bridge_result;
static uint32_t reg_read(void *unused, uint32_t offset)
{
    (void)unused;
    uint32_t value = Xil_In32((UINTPTR)0x43C00000U + offset);
    DATA_SYNC; return value;
}
static void reg_write(void *unused, uint32_t offset, uint32_t value)
{
    (void)unused; Xil_Out32((UINTPTR)0x43C00000U + offset, value); DATA_SYNC;
}
static int ready(void *unused)
{
    (void)unused; return !XUartPs_IsTransmitFull(XPAR_XUARTPS_0_BASEADDR);
}
static void send_byte(void *unused, unsigned char value)
{
    (void)unused; XUartPs_WriteReg(XPAR_XUARTPS_0_BASEADDR, XUARTPS_FIFO_OFFSET, value);
}

int main(void)
{
    XUartPs uart;
#ifdef SDT
    XUartPs_Config *config = XUartPs_LookupConfig(XPAR_XUARTPS_0_BASEADDR);
#else
    XUartPs_Config *config = XUartPs_LookupConfig(XPAR_XUARTPS_0_DEVICE_ID);
#endif
    if (!config || XUartPs_CfgInitialize(&uart, config, config->BaseAddress) != XST_SUCCESS) {
        ecg_bridge_result = -1; return 1;
    }
    XUartPsFormat format = {115200U, XUARTPS_FORMAT_8_BITS, XUARTPS_FORMAT_NO_PARITY, XUARTPS_FORMAT_1_STOP_BIT};
    if (XUartPs_SetDataFormat(&uart, &format) != XST_SUCCESS) {
        ecg_bridge_result = -2; return 1;
    }
    XUartPs_SetOperMode(&uart, XUARTPS_OPER_MODE_NORMAL);
    XUartPs_SetOptions(&uart, XUARTPS_OPTION_STOP_BREAK);
    XUartPs_SetInterruptMask(&uart, 0U);
    /* 显式使能TX/RX；所有协议字节仅由stream队列写出。 */
    u32 control = XUartPs_ReadReg(config->BaseAddress, XUARTPS_CR_OFFSET);
    control &= ~(XUARTPS_CR_TX_DIS | XUARTPS_CR_RX_DIS);
    control |= XUARTPS_CR_TX_EN | XUARTPS_CR_RX_EN;
    XUartPs_WriteReg(config->BaseAddress, XUARTPS_CR_OFFSET, control);
    /* XTime_GetTime只读计数器；使能计数但不清零、不改PS时钟/分频。 */
    u32 timer_control = Xil_In32(ECG_GLOBAL_TIMER_BASE + ECG_GLOBAL_TIMER_CONTROL);
    if (timer_control & 0xFF00U) { ecg_bridge_result = -6; return 1; }
    Xil_Out32(ECG_GLOBAL_TIMER_BASE + ECG_GLOBAL_TIMER_CONTROL, timer_control | 1U);
    XTime now; XTime_GetTime(&now);
    XTime start = now;
    /* BSP的COUNTS_PER_SECOND可能展开为无括号的CPU_FREQ/2，先求值为完整常量。 */
    const uint64_t timer_frequency = (uint64_t)(COUNTS_PER_SECOND);
    BridgeIo io = {NULL, reg_read, reg_write, ready, send_byte};
    ecg_bridge_init(&bridge, io);
    for (;;) {
        XTime_GetTime(&now);
        uint64_t elapsed = now-start;
        uint64_t us = ecg_bridge_time_us(elapsed, timer_frequency);
        /* RX/TX各有界推进；只在收到合法输入后才送PL，不生成任何样本。 */
        u32 errors = XUartPs_ReadReg(config->BaseAddress, XUARTPS_ISR_OFFSET);
        if (errors & (XUARTPS_IXR_OVER | XUARTPS_IXR_FRAMING | XUARTPS_IXR_PARITY)) {
            ecg_bridge_result=-7; return 1;
        }
        for (unsigned n=0; n<32 && XUartPs_IsReceiveData(config->BaseAddress); ++n) {
            u32 errors = XUartPs_ReadReg(config->BaseAddress, XUARTPS_ISR_OFFSET);
            if (errors & (XUARTPS_IXR_OVER | XUARTPS_IXR_FRAMING | XUARTPS_IXR_PARITY)) {
                ecg_bridge_result=-7; return 1;
            }
            unsigned char c = (unsigned char)XUartPs_ReadReg(config->BaseAddress, XUARTPS_FIFO_OFFSET);
            ecg_bridge_feed(&bridge, c, us);
        }
        if (ecg_bridge_step(&bridge, us)) break;
    }
    /* 只在停止送样后等待物理发送结束，并设2秒上限。 */
    XTime end = now;
    while (!XUartPs_IsTransmitEmpty(&uart) || XUartPs_IsSending(&uart)) {
        XTime_GetTime(&now);
        if (now - end > 2ULL * timer_frequency) { ecg_bridge_result = -4; return 1; }
    }
    ecg_bridge_result = bridge.failed ? -5 : 1;
    return bridge.failed ? 1 : 0;
}
