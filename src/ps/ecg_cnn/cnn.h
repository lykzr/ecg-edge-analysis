/* H27浮点裸机接口；不需要PyTorch运行时。 */
#ifndef ECG_CNN_H
#define ECG_CNN_H
#include <stdint.h>
#include "hgb.h"
typedef struct {uint32_t beat_id,position,ready_at,status,history_count;int32_t class_id;float logits[4],probability[4];} CnnResult;
extern const float cnn_weights[];
int cnn_forward(const float waveform[128],const float rr[3],const float hand[122],const float history[8],float logits[4]);
int cnn_record(const HgbRequest *requests,unsigned count,CnnResult *results);
#endif
