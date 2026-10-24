/* 500Hz完整C流程主机入口；stdout可选结构化请求，不补尾样。 */
#include "../src/ps/ecg_runtime/pipeline.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
static void output(EcgClassRequest*r,int n,int binary){for(int i=0;i<n;++i){if(binary)fwrite(&r[i],sizeof(r[i]),1,stdout);else printf("%u,%u,%u\n",r[i].ready_at,r[i].position,r[i].rr_samples);}}
int main(int argc,char**argv){
#ifdef _WIN32
 _setmode(_fileno(stdin),_O_BINARY);if(argc>1)_setmode(_fileno(stdout),_O_BINARY);
#endif
 int binary=argc>1&&!strcmp(argv[1],"requests");EcgPipeline*s=calloc(1,ecg_pipeline_size());float mean[3]={0},std[3]={1,1,1};if(!s||ecg_pipeline_init(s,1,mean,std))return 2;uint32_t seq=0;int16_t x;EcgClassRequest r[32];
 while(fread(&x,2,1,stdin)==1){int n=ecg_pipeline_push(s,x,seq++,r);if(n<0){fprintf(stderr,"pipeline_error=%d seq=%u\n",n,seq);return 3;}output(r,n,binary);}
 int n=ecg_pipeline_finish(s,r);if(n<0)return 4;output(r,n,binary);fprintf(stderr,"source_samples=%u events=%u state_bytes=%zu\n",seq,ecg_pipeline_events(s),ecg_pipeline_size());free(s);return ferror(stdin)?5:0;
}
