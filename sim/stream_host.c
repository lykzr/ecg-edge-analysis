/* 主机假外设：只验证PS流调度/队列/协议，不模拟真实QRS算法或UART驱动。 */
#include "stream.h"
#include <assert.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct {
    uint64_t now, next_tx, interval;
    uint32_t count, seq, pos, rr, queued, dropped, total, read_mask, pops;
    const char *mode;
} Fake;
static uint32_t read_reg(void *ctx, uint32_t offset)
{
    Fake *f = ctx;
    if (offset == 0x24) return strcmp(f->mode, "config") == 0 ? (ECG_STREAM_RATE_HZ == 500U ? 360U : 500U) : ECG_STREAM_RATE_HZ;
    if (offset == 0x28) return 120;
    if (offset == 0x2c) return 200;
    if (offset == 0x14) return 7168;
    if (offset == 0x30) return f->total;
    if (offset == 0x20) return f->dropped;
    if (offset == 0x1c) return f->queued;
    if (offset == 0x04) return f->queued != 0;
    if (offset == 0x08) { f->read_mask |= 1; return f->pos; }
    if (offset == 0x0c) { f->read_mask |= 2; return f->rr; }
    if (offset == 0x18) { f->read_mask |= 4; return f->seq; }
    return 0;
}
static void write_reg(void *ctx, uint32_t offset, uint32_t value)
{
    Fake *f = ctx;
    if (offset == 0x04) {
        assert(value == 1 && f->queued && f->read_mask == 7);
        --f->queued; ++f->pops; f->read_mask = 0;
        return;
    }
    assert(offset == 0);
    uint64_t due = ((uint64_t)f->count + 1) * 1000003U / ECG_STREAM_RATE_HZ;
    assert(f->now >= due && f->now - due < 1000003U / ECG_STREAM_RATE_HZ);
    int expected = (f->count >= 100 && (f->count - 100) % ECG_STREAM_RATE_HZ == 0) ?
                   (((f->count - 100)/ECG_STREAM_RATE_HZ)%2 ? -20000 : 20000) : 0;
    assert((int16_t)(uint16_t)value == expected);
    if (expected) {
        assert(!f->queued); f->queued = 1;
        f->pos = f->count - (ECG_STREAM_RATE_HZ * 120U / 1000U / 2U); f->rr = f->total ? ECG_STREAM_RATE_HZ : 0;
        f->seq = ++f->total;
        if (strcmp(f->mode, "zero_event") == 0) f->seq = f->pos = 0;
    }
    ++f->count;
}
static int ready(void *ctx)
{
    Fake *f = ctx;
    return strcmp(f->mode, "stalled") && f->now >= f->next_tx;
}
static void tx(void *ctx, unsigned char byte)
{
    Fake *f = ctx;
    putchar(byte); f->next_tx = f->now + f->interval;
}
int main(int argc, char **argv)
{
    Fake f = {0}; f.mode = argc > 1 ? argv[1] : "normal";
    f.interval = strcmp(f.mode, "slow") == 0 ? 1000 : 87;
    if (strcmp(f.mode, "dirty") == 0) f.total = 3;
    EcgIo io = {&f, read_reg, write_reg, ready, tx};
    EcgStream s;
    if (strcmp(f.mode, "invalid") == 0) {
        assert(!ecg_stream_init(&s, io, 0, 1000003, 10, "bad,session"));
        assert(!ecg_stream_init(&s, io, 0, 1000003, 0, "valid"));
        assert(!ecg_stream_init(&s, io, 0, 0, 10, "valid"));
        return 0;
    }
    uint32_t total = strcmp(f.mode, "short") == 0 ? 3 : (10U * ECG_STREAM_RATE_HZ + 3U);
    if (strcmp(f.mode, "zero_event") == 0) total = 200;
    assert(ecg_stream_init(&s, io, 0, 1000003, total, "host-test"));
    for (unsigned i = 0; i < 300000U; ++i) {
        f.now += 100;
        if (strcmp(f.mode, "deadline") == 0 && f.count == 20) f.now += 6000;
        if (ecg_stream_step(&s, f.now)) {
            fprintf(stderr, "RESULT samples=%" PRIu32 " pops=%" PRIu32 " drop=%" PRIu32
                    " failed=%u reason=%s max_late=%" PRIu64 " peak=%" PRIu32 "\n",
                    s.samples, f.pops, s.tx_drop, s.failed, s.error ? s.error : "completed", s.max_late, s.queue_peak);
            assert(s.samples == f.count && s.events == f.pops && s.queue_peak <= ECG_TX_CAPACITY);
            return s.failed ? 2 : 0;
        }
    }
    return 3;
}
