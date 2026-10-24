/* 主机候选入口：500Hz int16输入，可输出内部样本或源时轴事件；无EOF补零。 */
#include "../src/ps/ecg_rate500/rate500.h"
#include "../src/ps/ecg_runtime/runtime.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
int main(int argc,char**argv){
#ifdef _WIN32
 _setmode(_fileno(stdin),_O_BINARY);
#endif
 int samples=argc>1&&!strcmp(argv[1],"samples");EcgRate500 rate;ecg_rate500_init(&rate);EcgRuntime*s=calloc(1,ecg_runtime_size());if(!s)return 2;ecg_runtime_init(s);
 int16_t x,y;uint32_t seq=0,i;int64_t last=-1;EcgRuntimeEvent events[32];
 while(fread(&x,2,1,stdin)==1){int n=ecg_rate500_push(&rate,x,seq,&y,&i);if(n<0)return 3;
 if(n){if(samples)printf("%u,%d\n",i,y);else{int count=ecg_runtime_push(s,y,events);if(count<0)return 4;
 for(int k=0;k<count;++k){int64_t p=ecg_rate500_source(events[k].position);if(p<0)continue;if(last>=p)return 5;printf("%u,%lld,%lld\n",seq,(long long)p,(long long)(last<0?0:p-last));last=p;}}}++seq;}
 fprintf(stderr,"source_samples=%u internal_samples=%u clipped=%u tail_pending=%d\n",seq,rate.next_internal,rate.clipped,ecg_runtime_pending(s));free(s);return ferror(stdin)?6:0;
}
