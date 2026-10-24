#include "../src/ps/ecg_runtime/pipeline.h"
#include <stdio.h>
#include <stdlib.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
_Static_assert(sizeof(EcgClassRequest)==552,"测试文件布局变更须同步读取器");
int main(int argc,char**argv){
#ifdef _WIN32
 _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
#endif
 if(argc!=7)return 2;float mean[3],std[3];for(int i=0;i<3;++i){mean[i]=strtof(argv[i+1],0);std[i]=strtof(argv[i+4],0);}
 EcgPipeline*s=calloc(1,ecg_pipeline_size());if(!s||ecg_pipeline_init(s,1,mean,std))return 3;
 int16_t x;uint32_t seq=0;EcgClassRequest out[32];
 while(fread(&x,2,1,stdin)==1){int n=ecg_pipeline_push(s,x,seq++,out);if(n<0){free(s);return 4;}if(fwrite(out,sizeof(*out),(size_t)n,stdout)!=(size_t)n){free(s);return 5;}}
 int n=ecg_pipeline_finish(s,out);if(n<0){free(s);return 6;}fwrite(out,sizeof(*out),(size_t)n,stdout);free(s);return ferror(stdin)||ferror(stdout)?7:0;}
