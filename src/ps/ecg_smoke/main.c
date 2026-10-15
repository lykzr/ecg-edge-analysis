/* PS/AXI-Lite/检测器/FIFO 板上自检。输入是合成脉冲，不是 ECG 准确率测试。 */
#include "xil_io.h"
#include "xil_printf.h"
#include "sleep.h"

#define ECG_BASE ((UINTPTR)0x43C00000U)
#define SAMPLE 0x00U
#define STATUS 0x04U
#define INDEX 0x08U
#define RR 0x0CU
#define ENERGY 0x10U
#define THRESHOLD 0x14U
#define SEQUENCE 0x18U
#define QUEUED 0x1CU
#define DROPPED 0x20U
#define RATE 0x24U
#define WINDOW_MS 0x28U
#define REFRACTORY_MS 0x2CU
#define TOTAL 0x30U

static u32 failures;

static u32 read_reg(u32 offset)
{
    u32 value = Xil_In32(ECG_BASE + offset);
    DATA_SYNC;
    return value;
}

static void write_reg(u32 offset, u32 value)
{
    Xil_Out32(ECG_BASE + offset, value);
    DATA_SYNC;
}

static int expect(const char *name, u32 actual, u32 expected)
{
    if (actual == expected) return 1;
    xil_printf("FAIL %s got=%u expected=%u\r\n", name, actual, expected);
    ++failures;
    return 0;
}

/* 先完整读取队首，再弹出；本程序是唯一消费者。 */
static int check_head(u32 index, u32 rr, u32 sequence)
{
    u32 actual_index = read_reg(INDEX);
    u32 actual_rr = read_reg(RR);
    u32 actual_sequence = read_reg(SEQUENCE);
    int ok = expect("index", actual_index, index);
    ok &= expect("rr", actual_rr, rr);
    ok &= expect("sequence", actual_sequence, sequence);
    return ok;
}

/* 每次 32 位写仅低 16 位是样本，保留有符号数的二进制表示。 */
static void sample(s16 value)
{
    write_reg(SAMPLE, (u32)(u16)value);
}

static void zeros(u32 count)
{
    for (u32 i = 0; i < count; ++i) sample(0);
}

/* 一个 ±20000 脉冲加 359 个零。相邻事件的样本间距应为 360。 */
static int pulse_period(u32 ordinal)
{
    sample((ordinal & 1U) ? (s16)-20000 : (s16)20000);
    usleep(10); /* 等待样本经过检测器流水线，再读积分值。 */
    if (!expect("pulse_energy", read_reg(ENERGY), 20000U)) return 0;
    zeros(359U);
    usleep(10);
    return expect("settled_energy", read_reg(ENERGY), 0U);
}

int main(void)
{
    xil_printf("\r\nBEGIN ECG_SMOKE base=0x43C00000\r\n");
    xil_printf("Synthetic samples; no ADC; no clinical accuracy claim.\r\n");
    u32 rate = read_reg(RATE);
    u32 window = read_reg(WINDOW_MS);
    u32 refractory = read_reg(REFRACTORY_MS);
    xil_printf("CONFIG rate=%u window_ms=%u refractory_ms=%u\r\n",
               rate, window, refractory);
    int ok = expect("rate", rate, 360U);
    ok &= expect("window_ms", window, 120U);
    ok &= expect("refractory_ms", refractory, 200U);
    if (!ok) goto done;
    xil_printf("PASS CONFIG\r\n");

    /* 无软件复位寄存器；必须通过 Run 的 Program Device 重新配置 PL。 */
    ok = expect("initial_status", read_reg(STATUS), 0U);
    ok &= expect("initial_queue", read_reg(QUEUED), 0U);
    ok &= expect("initial_total", read_reg(TOTAL), 0U);
    ok &= expect("initial_dropped", read_reg(DROPPED), 0U);
    ok &= expect("initial_energy", read_reg(ENERGY), 0U);
    ok &= expect("initial_threshold", read_reg(THRESHOLD), 7168U);
    if (!ok) {
        xil_printf("Need fresh PL: enable Program Device and rerun.\r\n");
        goto done;
    }

    zeros(100U);
    usleep(10);
    ok = expect("zero_total", read_reg(TOTAL), 0U);
    ok &= expect("zero_energy", read_reg(ENERGY), 0U);
    if (!ok) goto done;
    xil_printf("PASS ZERO_INPUT\r\n");

    /* 43 点积分窗口回移 21 点：首事件位置 100-21=79。 */
    for (u32 i = 0; i < 4U; ++i) {
        if (!pulse_period(i)) goto done;
        ok = expect("normal_status", read_reg(STATUS), 1U);
        ok &= expect("normal_queue", read_reg(QUEUED), 1U);
        ok &= expect("normal_total", read_reg(TOTAL), i + 1U);
        ok &= expect("normal_dropped", read_reg(DROPPED), 0U);
        ok &= check_head(79U + 360U * i, i ? 360U : 0U, i + 1U);
        if (!ok) goto done;
        xil_printf("EVENT seq=%u index=%u rr=%u\r\n",
                   i + 1U, 79U + 360U * i, i ? 360U : 0U);
        write_reg(STATUS, 1U);
        if (!expect("normal_pop", read_reg(QUEUED), 0U)) goto done;
    }
    xil_printf("PASS EVENT_FIELDS_AND_POP\r\n");

    /* 下一段从样本 1540 开始；不消费，检查队首保持和满队列丢弃。 */
    for (u32 i = 0; i < 12U; ++i) {
        if (!pulse_period(i)) goto done;
        u32 produced = i + 1U;
        u32 queued = produced < 8U ? produced : 8U;
        u32 dropped = produced > 8U ? produced - 8U : 0U;
        ok = expect("burst_queue", read_reg(QUEUED), queued);
        ok &= expect("burst_total", read_reg(TOTAL), 4U + produced);
        ok &= expect("burst_dropped", read_reg(DROPPED), dropped);
        ok &= expect("burst_status", read_reg(STATUS), dropped ? 3U : 1U);
        ok &= check_head(1519U, 360U, 5U);
        if (!ok) goto done;
    }
    xil_printf("PASS FIFO_OVERFLOW queued=8 total=16 dropped=4\r\n");

    /* 清提示不能清累计丢弃数，也不能弹出队首。 */
    write_reg(STATUS, 2U);
    ok = expect("clear_status", read_reg(STATUS), 1U);
    ok &= expect("clear_queue", read_reg(QUEUED), 8U);
    ok &= expect("clear_dropped", read_reg(DROPPED), 4U);
    if (!ok) goto done;
    for (u32 i = 0; i < 8U; ++i) {
        if (!check_head(1519U + 360U * i, 360U, 5U + i)) goto done;
        write_reg(STATUS, 1U);
        if (!expect("burst_pop", read_reg(QUEUED), 7U - i)) goto done;
    }
    ok = expect("empty_status", read_reg(STATUS), 0U);
    ok &= expect("empty_index", read_reg(INDEX), 0U);
    ok &= expect("empty_rr", read_reg(RR), 0U);
    ok &= expect("empty_sequence", read_reg(SEQUENCE), 0U);
    ok &= expect("final_total", read_reg(TOTAL), 16U);
    ok &= expect("final_dropped", read_reg(DROPPED), 4U);
    if (!ok) goto done;
    xil_printf("PASS FIFO_DRAIN_AND_OVERFLOW_CLEAR\r\n");

done:
    xil_printf("%s ECG_SMOKE failures=%u\r\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 1 : 0;
}
