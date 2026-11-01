#include "legacy.h"
#include "link.h"
#include <string.h>
static RuntimeLink link_state;
static union {double align;unsigned char bytes[192U*1024U];} storage;
int hgb_legacy_run(const char *header,void *ctx,uint64_t (*clock)(void *),
                  int (*receive)(void *,unsigned char *),int (*ready)(void *),
                  void (*send)(void *,unsigned char))
{
    if(ecg_pipeline_size()>sizeof(storage.bytes))return -1;
    RuntimeIo io={ctx,ready,send};
    ecg_link_init(&link_state,io,(EcgPipeline *)storage.bytes,0);
    if(link_state.failed)return -1;
    /* 外层已广播同一就绪头；不在当前握手内重复启动头。 */
    link_state.head=link_state.used=0;
    uint64_t now=clock(ctx);
    for(const char *p=header;*p;p++)ecg_link_feed(&link_state,(unsigned char)*p,now);
    ecg_link_feed(&link_state,'\n',now);
    for(;;){
        now=clock(ctx);
        for(unsigned i=0;i<32;i++){
            unsigned char c;int got=receive(ctx,&c);
            if(got<0)return -1;
            if(!got)break;
            ecg_link_feed(&link_state,c,now);
        }
        if(ecg_link_step(&link_state,now))return link_state.failed?-1:0;
    }
}
