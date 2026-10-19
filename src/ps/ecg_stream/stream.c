#include "stream.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static void fail(EcgStream *s, const char *reason, uint64_t now)
{
    if (!s->failed) { s->failed = 1; s->error = reason; }
    if (s->phase == 0) { s->phase = 1; s->drain_start = now; }
}

static int enqueue(EcgStream *s, const char *line, int wave)
{
    unsigned n = (unsigned)strlen(line);
    unsigned reserve = wave ? ECG_TX_CAPACITY / 8U : 0;
    if (n == 0 || n > 256U || n + reserve > ECG_TX_CAPACITY - s->used) return 0;
    for (unsigned i = 0; i < n; ++i)
        s->queue[(s->head + s->used + i) % ECG_TX_CAPACITY] = (unsigned char)line[i];
    s->used += n;
    if (s->used > s->queue_peak) s->queue_peak = s->used;
    return 1;
}

static int header(EcgStream *s)
{
    char line[192];
    snprintf(line, sizeof(line), "H,ECG-UART-1,ps-stream-2,%s,SYNTH,QRS-ORIG-%" PRIu32 ",%" PRIu32 ",-1,0xD\n",
             s->session, s->rate * 120U / 1000U, s->rate);
    return enqueue(s, line, 0);
}

static void wave(EcgStream *s)
{
    char line[160];
    int n = snprintf(line, sizeof(line), "W,%" PRIu32 ",%u", s->samples - s->batch_n, s->batch_n);
    for (unsigned i = 0; i < s->batch_n; ++i)
        n += snprintf(line + n, sizeof(line) - (unsigned)n, ",%d,NA", (int)s->batch[i]);
    snprintf(line + n, sizeof(line) - (unsigned)n, "\n");
    if (!enqueue(s, line, 1)) s->tx_drop += s->batch_n;
    s->batch_n = 0;
}

static int status(EcgStream *s, uint64_t now)
{
    char line[192];
    uint32_t dropped = s->io.read_reg(s->io.context, 0x20U);
    const char *flags = dropped ? (s->tx_drop ? "OVF|TX_DROP" : "OVF") : (s->tx_drop ? "TX_DROP" : "NA");
    /* 未实现信号质量/ADC状态，不能用OK声称整个系统正常。T不缓存过期心率。 */
    snprintf(line, sizeof(line), "T,-1,-1,?,%s,%" PRIu32 ",%" PRIu32 ",0,%" PRIu32 ",%" PRIu32 "\n",
             flags, s->rate, dropped, s->tx_drop, (uint32_t)((now - s->start) * 1000U / s->frequency));
    return enqueue(s, line, 0);
}

int ecg_stream_init(EcgStream *s, EcgIo io, uint64_t now, uint64_t frequency,
                    uint32_t total, const char *session)
{
    size_t len = session ? strlen(session) : 0;
    if (!s || !io.read_reg || !io.write_reg || !io.tx_ready || !io.tx_byte ||
        (ECG_STREAM_RATE_HZ != 360U && ECG_STREAM_RATE_HZ != 500U) ||
        frequency < ECG_STREAM_RATE_HZ || frequency > 1000000000U || total == 0 || total > 1800000U ||
        len == 0 || len > 32) return 0;
    for (size_t i = 0; i < len; ++i) {
        char c = session[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '.')) return 0;
    }
    memset(s, 0, sizeof(*s)); s->io = io; s->frequency = frequency;
    s->start = s->last = s->last_tx = now; s->total = total; s->rate = ECG_STREAM_RATE_HZ;
    memcpy(s->session, session, len + 1);
    if (!header(s)) return 0;
    if (io.read_reg(io.context, 0x24U) != s->rate || io.read_reg(io.context, 0x28U) != 120U ||
        io.read_reg(io.context, 0x2cU) != 200U) fail(s, "CONFIG_MISMATCH", now);
    else if (io.read_reg(io.context, 0x04U) || io.read_reg(io.context, 0x1cU) ||
             io.read_reg(io.context, 0x30U) || io.read_reg(io.context, 0x20U) ||
             io.read_reg(io.context, 0x10U) || io.read_reg(io.context, 0x14U) != 7168U)
        fail(s, "NEED_FRESH_PL", now);
    return 1;
}

int ecg_stream_step(EcgStream *s, uint64_t now)
{
    if (s->phase == 4) return 1;
    if (now < s->last) { s->failed = 1; s->error = "CLOCK_REVERSED"; s->phase = 4; return 1; }
    s->last = now;
    uint64_t elapsed = now - s->start;
    if (s->phase == 0) {
        uint64_t due = ((uint64_t)s->samples + 1U) * s->frequency / s->rate;
        if (elapsed >= due) {
            uint64_t late = elapsed - due;
            if (late > s->max_late) s->max_late = late;
            if (late >= s->frequency / s->rate) fail(s, "SAMPLE_DEADLINE_MISSED", now);
            else {
                uint32_t i = s->samples;
                int16_t value = (i >= 100U && (i - 100U) % s->rate == 0) ?
                                (((i - 100U) / s->rate) % 2U ? -20000 : 20000) : 0;
                s->io.write_reg(s->io.context, 0x00U, (uint16_t)value);
                s->batch[s->batch_n++] = value; ++s->samples;
                if (s->batch_n == 8U) wave(s);
                if (s->samples == s->total) { s->phase = 1; s->drain_start = now; }
            }
        }
    }
    /* 唯一FIFO消费者：完整读队首，成功入发送队列后才弹出，不按值0判空。 */
    if (s->phase <= 1 && !s->failed) {
        for (unsigned i = 0; i < 8U && (s->io.read_reg(s->io.context, 0x04U) & 1U); ++i) {
            uint32_t pos = s->io.read_reg(s->io.context, 0x08U);
            uint32_t rr = s->io.read_reg(s->io.context, 0x0cU);
            uint32_t seq = s->io.read_reg(s->io.context, 0x18U);
            char hr[40], line[160];
            if (rr) {
                uint64_t tenths = (600ULL * s->rate + rr / 2U) / rr;
                snprintf(hr, sizeof(hr), "%" PRIu64 ".%" PRIu64, tenths / 10U, tenths % 10U);
            } else strcpy(hr, "-1");
            snprintf(line, sizeof(line), "E,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%s,?,-1\n", seq, pos, rr, hr);
            if (!enqueue(s, line, 0)) { fail(s, "EVENT_TX_QUEUE_FULL", now); break; }
            s->io.write_reg(s->io.context, 0x04U, 1U); ++s->events;
        }
    }
    if (s->phase == 0 && elapsed / s->frequency > s->periodic) {
        s->periodic = (uint32_t)(elapsed / s->frequency);
        /* 相同H每秒重发，PC中途打开可获元数据；不是心跳停流机制。 */
        if (!header(s) || !status(s, now)) fail(s, "CONTROL_TX_QUEUE_FULL", now);
    }
    if (s->phase == 1 && now - s->drain_start >= s->frequency / 1000U + 1U) {
        if (s->batch_n) wave(s);
        s->phase = 2;
    }
    if (s->phase == 2 && s->used == 0) {
        char line[256];
        status(s, now);
        snprintf(line, sizeof(line), "L,%c,END reason=%s samples=%" PRIu32 " events=%" PRIu32
                 " tx_sample_drop=%" PRIu32 " queue_peak=%" PRIu32 " max_late_ticks=%" PRIu64 " timer_hz=%" PRIu64 "\n",
                 s->failed ? 'E' : 'I', s->error ? s->error : "completed", s->samples, s->events,
                 s->tx_drop, s->queue_peak, s->max_late, s->frequency);
        enqueue(s, line, 0); s->phase = 3;
    }
    for (unsigned n = 0; n < 32U && s->used && s->io.tx_ready(s->io.context); ++n) {
        s->io.tx_byte(s->io.context, s->queue[s->head]);
        s->head = (s->head + 1U) % ECG_TX_CAPACITY; --s->used; s->last_tx = now;
    }
    if (s->used && now - s->last_tx >= 2U * s->frequency) {
        s->failed = 1; s->error = "UART_STALLED"; s->phase = 4; return 1;
    }
    if (!s->used && s->phase == 3) { s->phase = 4; return 1; }
    return 0;
}
