/* 有界、单线程的数字合成流；硬件操作通过回调隔离以供主机故障注入。 */
#ifndef ECG_STREAM_H
#define ECG_STREAM_H
#include <stdint.h>
#ifndef ECG_STREAM_RATE_HZ
#define ECG_STREAM_RATE_HZ 500U
#endif
#ifndef ECG_TX_CAPACITY
#define ECG_TX_CAPACITY 8192U
#endif
typedef struct {
    void *context;
    uint32_t (*read_reg)(void *, uint32_t);
    void (*write_reg)(void *, uint32_t, uint32_t);
    int (*tx_ready)(void *);
    void (*tx_byte)(void *, unsigned char);
} EcgIo;
typedef struct {
    EcgIo io;
    uint64_t start, last, frequency, drain_start, last_tx, max_late;
    uint32_t samples, total, rate, tx_drop, queue_peak, events, periodic;
    unsigned phase, failed, batch_n, used, head;
    int16_t batch[8];
    char session[33];
    unsigned char queue[ECG_TX_CAPACITY];
    const char *error;
} EcgStream;
/* 返回0表示初始化拒绝。调用者仍须每次系统复位并重新配置PL。 */
int ecg_stream_init(EcgStream *, EcgIo, uint64_t now, uint64_t frequency,
                    uint32_t total, const char *session);
/* 返回1表示结束；failed/error是结果，软件队列清空不等于物理线传完。 */
int ecg_stream_step(EcgStream *, uint64_t now);
#endif
