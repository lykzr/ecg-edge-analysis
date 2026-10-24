
#include "pipeline.h"
#include "resample360.h"
#include <math.h>
#include <string.h>
typedef struct {uint32_t id,pos,rr;float basic[3];} Pending;
struct EcgPipeline {uint32_t generation,index,events,head,used,rrhead,rrused,closed;int16_t raw[4096];uint32_t history[401];float mean[3],std[3];Pending pending[32];};
static size_t offset(void){return (sizeof(EcgPipeline)+7U)&~(size_t)7U;}
static EcgRuntime* detector(EcgPipeline*s){return (EcgRuntime*)((unsigned char*)s+offset());}
size_t ecg_pipeline_size(void){return offset()+ecg_runtime_size();}
uint32_t ecg_pipeline_events(const EcgPipeline*s){return s->events;}
int ecg_pipeline_init(EcgPipeline*s,uint32_t gen,const float mean[3],const float std[3]){
 float test[3],input[3]={0};if(!s||!gen||ecg_class_normalize_rr(input,mean,std,test))return -1;
 memset(s,0,ecg_pipeline_size());s->generation=gen;s->index=UINT32_MAX;memcpy(s->mean,mean,12);memcpy(s->std,std,12);ecg_runtime_init(detector(s));return 0;}
static void request(EcgPipeline*s,const Pending*p,EcgClassRequest*r){memset(r,0,sizeof(*r));r->generation=s->generation;r->beat_id=p->id;r->position=p->pos;r->rr_samples=p->rr;r->sampling_hz=360;r->ready_at=s->index;}
static int window(EcgPipeline*s,const Pending*p,EcgClassRequest*r){request(s,p,r);double sampled[128],sum=0.,variance=0.;
 if(p->pos<128||p->pos+191>s->index||s->index-(p->pos-128)>=4096){r->input_status=ECG_CLASS_WINDOW_INCOMPLETE;return 0;}
 for(int m=0;m<128;++m){double v=0.;int time=m*5+50;
  for(int k=0;k<320;++k){int h=time-k*2;if(h>=0&&h<=100)v+=((double)s->raw[(p->pos-128+(uint32_t)k)%4096]/4096.)*ecg_resample360[h];}sampled[m]=v;sum+=v;}
 double mean=sum/128.;for(int i=0;i<128;++i){sampled[i]-=mean;variance+=sampled[i]*sampled[i];}double std=sqrt(variance/128.);if(std<.05)std=.05;
 for(int i=0;i<128;++i)r->waveform[i]=(float)(sampled[i]/std);
 if(!p->rr){r->input_status=ECG_CLASS_MISSING_RR;return 0;}
 return ecg_class_normalize_rr(p->basic,s->mean,s->std,r->rr);
}
int ecg_pipeline_push(EcgPipeline*s,int16_t x,uint32_t seq,EcgClassRequest out[32]){
 if(!s||!out||s->closed||seq!=s->index+1U||seq>=1800000)return -1;
 s->index=seq;s->raw[seq%4096]=x;EcgRuntimeEvent events[32];int n=ecg_runtime_push(detector(s),x,events);if(n<0)return n;
 for(int i=0;i<n;++i){if(s->used==32)return -2;EcgRuntimeEvent*e=&events[i];Pending*p=&s->pending[(s->head+s->used++)%32];memset(p,0,sizeof(*p));p->id=++s->events;p->pos=e->position;p->rr=e->rr;
  if(e->rr){double local=0.,global=0.;unsigned past=s->rrused<400?s->rrused:400,ln=past<80?past:80;
   for(unsigned j=0;j<past;++j){unsigned at=(s->rrhead+s->rrused-1-j)%401;global+=s->history[at];if(j<ln)local+=s->history[at];}
   local=ln?local/ln:e->rr;global=past?global/past:e->rr;double values[3]={e->rr/local,e->rr/global,local/global};
   for(int j=0;j<3;++j){if(values[j]<0)values[j]=0;if(values[j]>4)values[j]=4;p->basic[j]=(float)values[j]/4.f;}
   if(s->rrused==401){s->rrhead=(s->rrhead+1)%401;--s->rrused;}s->history[(s->rrhead+s->rrused++)%401]=e->rr;
  }}
 int count=0;while(s->used){Pending*p=&s->pending[s->head];if(p->pos>=128&&p->pos+191>s->index)break;
  if(window(s,p,&out[count++]))return -3;s->head=(s->head+1)%32;--s->used;}
 return count;
}
int ecg_pipeline_finish(EcgPipeline*s,EcgClassRequest out[32]){if(!s||!out||s->closed)return -1;int n=0;while(s->used){request(s,&s->pending[s->head],&out[n]);out[n++].input_status=ECG_CLASS_WINDOW_INCOMPLETE;s->head=(s->head+1)%32;--s->used;}s->closed=1;return n;}
