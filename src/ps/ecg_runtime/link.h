#ifndef ECG_RUNTIME_LINK_H
#define ECG_RUNTIME_LINK_H
#include "pipeline.h"
typedef struct {void*ctx;int(*ready)(void*);void(*byte)(void*,unsigned char);} RuntimeIo;
typedef struct {RuntimeIo io;EcgPipeline*pipeline;EcgClassState classifier;char line[256],session[33],source[8];unsigned len,active,busy,done,failed,count,cursor,head,used,trace,peak;uint32_t samples,events;uint64_t now,last_rx,last_tx,periodic;int16_t data[32];unsigned char tx[8192];const char*error;} RuntimeLink;
void ecg_link_init(RuntimeLink*,RuntimeIo,EcgPipeline*,unsigned);
void ecg_link_feed(RuntimeLink*,unsigned char,uint64_t);
int ecg_link_step(RuntimeLink*,uint64_t);
#endif
