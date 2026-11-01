#ifndef HGB_LEGACY_H
#define HGB_LEGACY_H
#include <stdint.h>
/* 在独立编译单元链接已验500Hz流式核心，避免与模型冻结检测器混用。 */
int hgb_legacy_run(const char *, void *, uint64_t (*)(void *),
                   int (*)(void *, unsigned char *), int (*)(void *),
                   void (*)(void *, unsigned char));
#endif
