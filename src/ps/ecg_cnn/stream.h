/* 有界连续输入：检测/高通状态跨传输块延续，停止只标记不完整窗口。 */
#ifndef ECG_CNN_STREAM_H
#define ECG_CNN_STREAM_H
#include "cnn.h"
size_t cnn_input_stream_size(void);
int cnn_input_stream_init(void *state);
int cnn_input_stream_push(void *state,int16_t code,uint32_t index,HgbRequest out[32]);
int cnn_input_stream_finish(void *state,HgbRequest out[32]);
typedef struct {
    float background[8][128],pending_wave[32][128];
    uint32_t pending_ready[32],positions[33],last_id,last_ready,last_position;
    unsigned backgrounds,pending_count,position_count;
} CnnHistory;
void cnn_history_init(CnnHistory *state);
int cnn_history_push(CnnHistory *state,const HgbRequest *request,CnnResult *result);
#endif
