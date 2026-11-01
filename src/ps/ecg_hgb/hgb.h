/* v92研究模型的可移植C接口；不依赖Python、操作系统或板级外设。 */
#ifndef ECG_HGB_H
#define ECG_HGB_H
#include <stddef.h>
#include <stdint.h>
#define ECG_HGB_FEATURES 192
#define ECG_HGB_CLASSES 3
#define ECG_HGB_MAX_EVENTS 30000
typedef struct {
    uint32_t generation, beat_id, position, rr_samples, sampling_hz, ready_at, input_status;
    float waveform[128], rr[3];
} HgbRequest;
typedef struct {
    uint32_t beat_id, position, decision_at, status, history_count;
    int32_t class_id;
    float features[192];
    double probability[3];
} HgbResult;
/* 原权重保留double阈值/叶值；整数仅用于节点索引，尚未INT8量化。 */
typedef struct { double value, threshold; uint32_t left, right; uint16_t feature; uint8_t leaf; } HgbNode;
extern const HgbNode hgb_nodes[];
extern const uint32_t hgb_tree_offsets[193];
extern const double hgb_baseline[3];
extern const float hgb_hermite_basis[37][6];
extern const char hgb_model_sha256[], hgb_config_sha256[];
int ecg_hgb_probability(const float features[192], double probability[3]);
/* 整段离线对齐入口：requests须来自冻结模型重切拍，不能直接塞板端原窗口。
   输入/输出由调用者持有；无malloc，固定局部缓存。不是连续送样应用。 */
int ecg_hgb_record(const HgbRequest *requests, size_t count, uint32_t samples, HgbResult *results);
/* 冻结模型原检测→能量定位→重切拍的整段C入口。workspace须8字节对齐。
   输入为已完成固定高通、4096单位/mV的int16，不重复高通。
   容量不足或合同错误返回负值，不能忽略后作为完整结果。 */
size_t ecg_hgb_workspace_size(uint32_t samples);
int ecg_hgb_prepare(const int16_t *codes,uint32_t samples,HgbRequest *requests,
                    uint32_t capacity,void *workspace,size_t bytes,uint32_t *events);
/* 与模型hp05相同的顺序滤波/量化；count=0允许空块，不重置状态。 */
typedef struct {double previous_input,previous_output;uint32_t clipped,started,highpass;} HgbInput;
int ecg_hgb_input(HgbInput *state,const double *mv,size_t count,int highpass,int16_t *codes);
#endif
