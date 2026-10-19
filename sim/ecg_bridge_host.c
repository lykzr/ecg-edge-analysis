/* 只暴露测试状态，行为来自正式bridge.c；不实现另一份协议。 */
#include "bridge.h"
#include <stddef.h>
size_t ecg_bridge_size(void) {return sizeof(EcgBridge);}
uint32_t ecg_bridge_field(EcgBridge *s, unsigned n)
{
    switch(n) {case 0:return s->samples;case 1:return s->failed;case 2:return s->done;
    case 3:return s->peak;case 4:return s->events;default:return 0;}
}
const char *ecg_bridge_error(EcgBridge *s) {return s->error?s->error:"";}
