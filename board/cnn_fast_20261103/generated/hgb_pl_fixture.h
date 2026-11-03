#include <stdint.h>
typedef struct {int64_t value;uint32_t threshold;uint16_t left,right;uint8_t feature,leaf;} HgbQNode;
extern const int64_t hgb_qbaseline[3];
extern const HgbQNode hgb_qnodes[3][4096];
extern const uint16_t hgb_qroots[3][64];
extern const uint32_t hgb_test_features[160][192];
extern const int64_t hgb_test_scores[160][3];
