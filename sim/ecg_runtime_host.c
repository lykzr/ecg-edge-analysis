/* C移植候选主机入口：stdin为int16小端，stdout逐事件CSV。 */
#include "../src/ps/ecg_runtime/runtime.h"
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
int main(void){
#ifdef _WIN32
 _setmode(_fileno(stdin),_O_BINARY);
#endif
 EcgRuntime*s=calloc(1,ecg_runtime_size());if(!s)return 2;ecg_runtime_init(s);
 int16_t x;EcgRuntimeEvent e[32];while(fread(&x,sizeof(x),1,stdin)==1){int n=ecg_runtime_push(s,x,e);if(n<0){fprintf(stderr,"runtime_error=%d\n",n);free(s);return 3;}
 for(int i=0;i<n;++i)printf("%u,%u,%u\n",e[i].emitted,e[i].position,e[i].rr);}
 fprintf(stderr,"tail_pending=%d state_bytes=%zu\n",ecg_runtime_pending(s),ecg_runtime_size());free(s);return ferror(stdin)?4:0;}
