/* 主机CPU计时：两个独立回放，pipeline含QRS，不允许相减当切拍耗时。 */
#include "../src/ps/ecg_runtime/pipeline.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
int main(void){
 const unsigned n=36000;int16_t *x=calloc(n,sizeof(*x));
 EcgRuntime*r=calloc(1,ecg_runtime_size());EcgPipeline*p=calloc(1,ecg_pipeline_size());
 if(!x||!r||!p)return 2;
 for(unsigned i=0;i<n;++i)x[i]=(i%288==150)?18000:0;
 ecg_runtime_init(r);EcgRuntimeEvent e[32];unsigned count=0,maxwait=0;unsigned long long waits=0;
 clock_t a=clock();if(a==(clock_t)-1)return 3;
 for(unsigned i=0;i<n;++i){int k=ecg_runtime_push(r,x[i],e);if(k<0)return 4;
  for(int j=0;j<k;++j){unsigned w=e[j].emitted-e[j].position;count++;waits+=w;if(w>maxwait)maxwait=w;}}
 double qrs=(double)(clock()-a)/CLOCKS_PER_SEC;
 float mean[3]={0,0,0},std[3]={1,1,1};if(ecg_pipeline_init(p,1,mean,std))return 5;
 EcgClassRequest out[32];unsigned requests=0,readymax=0;unsigned long long ready=0;
 a=clock();
 for(unsigned i=0;i<n;++i){int k=ecg_pipeline_push(p,x[i],i,out);if(k<0)return 6;
  for(int j=0;j<k;++j){unsigned w=out[j].ready_at-out[j].position;requests++;ready+=w;if(w>readymax)readymax=w;}}
 int tail=ecg_pipeline_finish(p,out);if(tail<0)return 7;
 double pipeline=(double)(clock()-a)/CLOCKS_PER_SEC;
 printf("{\"samples\":%u,\"events\":%u,\"requests\":%u,\"tail_invalid\":%d,\"qrs_cpu_s\":%.9f,\"pipeline_including_qrs_cpu_s\":%.9f,\"qrs_wait_mean_samples\":%.9f,\"qrs_wait_max_samples\":%u,\"window_ready_mean_samples\":%.9f,\"window_ready_max_samples\":%u,\"clock_ticks_per_second\":%ld}\n",n,count,requests,tail,qrs,pipeline,count?(double)waits/count:0,maxwait,requests?(double)ready/requests:0,readymax,(long)CLOCKS_PER_SEC);
 free(x);free(r);free(p);return 0;
}
