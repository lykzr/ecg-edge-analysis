/* 仅主机布局核验；不属于板上应用。 */
#include "../src/ps/ecg_classification/classification.h"
#include <stddef.h>
_Static_assert(sizeof(float)==4,"float32 required");
size_t ecg_class_state_size(void){return sizeof(EcgClassState);}
size_t ecg_class_request_size(void){return sizeof(EcgClassRequest);}
size_t ecg_class_result_size(void){return sizeof(EcgClassResult);}
