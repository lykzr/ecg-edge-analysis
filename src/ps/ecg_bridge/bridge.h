/* ECG-IN-1输入核心：单会话、有界缓存，不生成样本、不执行ADC驱动。 */
#ifndef ECG_BRIDGE_H
#define ECG_BRIDGE_H
#include <stdint.h>
typedef struct {
    void *ctx;
    uint32_t (*read_reg)(void *, uint32_t);
    void (*write_reg)(void *, uint32_t, uint32_t);
    int (*tx_ready)(void *);
    void (*tx_byte)(void *, unsigned char);
} BridgeIo;
typedef struct {
    BridgeIo io;
    char line[256], session[33], source[8];
    unsigned len, active, busy, done, failed, count, cursor, head, used;
    uint32_t samples, events, peak;
    uint64_t last, last_rx, last_tx, tail, periodic;
    int16_t data[32];
    unsigned char tx[8192];
    const char *error;
} EcgBridge;
void ecg_bridge_init(EcgBridge *, BridgeIo);
void ecg_bridge_feed(EcgBridge *, unsigned char, uint64_t now_us);
/* 非阻塞推进接收后的送样/FIFO/发送；返回1表示本会话结束。 */
int ecg_bridge_step(EcgBridge *, uint64_t now_us);
#endif
