#ifndef ECG_RUNTIME_LINK_H
#define ECG_RUNTIME_LINK_H
#include "pipeline.h"
typedef struct {void*ctx;int(*ready)(void*);void(*byte)(void*,unsigned char);} RuntimeIo;
typedef struct {RuntimeIo io;EcgPipeline*pipeline;EcgClassState classifier;char line[256],session[33],source[8];unsigned len,active,busy,done,failed,count,cursor,head,used,trace,peak;uint32_t samples,events,last_rr;uint64_t now,last_rx,last_tx,periodic;int16_t data[32];unsigned char tx[8192];const char*error;} RuntimeLink;
void ecg_link_init(RuntimeLink*,RuntimeIo,EcgPipeline*,unsigned);
/* 仅完整结束且发送队列清空后开启新会话；错误保持锁存。 */
int ecg_link_rearm(RuntimeLink*,uint64_t);
void ecg_link_feed(RuntimeLink*,unsigned char,uint64_t);
int ecg_link_step(RuntimeLink*,uint64_t);
#endif
