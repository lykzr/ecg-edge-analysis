#include "../src/ps/ecg_runtime/link.h"
size_t ecg_link_size(void){return sizeof(RuntimeLink);}
unsigned ecg_link_peak(const RuntimeLink*s){return s->peak;}
unsigned ecg_link_failed(const RuntimeLink*s){return s->failed;}
const char*ecg_link_error(const RuntimeLink*s){return s->error;}
