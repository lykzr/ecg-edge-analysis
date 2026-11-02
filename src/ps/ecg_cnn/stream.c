/* 冻结500Hz检测器的在线能量定位与重切拍；有界环形缓存，无前缀重算。 */
#include "stream.h"
#include "pipeline.h"
#include "rate500.h"
#include "window500.h"
#include <math.h>
#include <string.h>
typedef struct {
    EcgRate500 rate;
    uint32_t index,filtered_count,last_position,last_ready,rr[401];
    unsigned count,rr_count,rr_head,pending_count,closed;
    int16_t raw[4096],filtered[4096];
    HgbRequest pending[32];
} InputStream;
static size_t aligned(void){return (sizeof(InputStream)+7U)&~(size_t)7U;}
static EcgPipeline *pipeline(InputStream *s){return (EcgPipeline*)((unsigned char*)s+aligned());}
size_t cnn_input_stream_size(void){return aligned()+ecg_pipeline_size();}
int cnn_input_stream_init(void *state){
    if(!state||((uintptr_t)state&7U))return -1;
    InputStream*s=state;memset(s,0,cnn_input_stream_size());s->index=UINT32_MAX;
    const float zero[3]={0},one[3]={1,1,1};ecg_rate500_init(&s->rate);
    return ecg_pipeline_init(pipeline(s),1,zero,one);
}
static int enqueue(InputStream*s,const HgbRequest *in){
    if(s->pending_count==32)return -1;
    HgbRequest q=*in;uint32_t pos=q.position,m=(uint32_t)(((uint64_t)pos*18+12)/25+20);
    if(m>=36&&(uint64_t)m+36<s->filtered_count&&((uint64_t)(m+36)*25+17)/18<=q.ready_at){
        if(s->filtered_count-(m-36)>4096)return -1;
        int64_t mass=0,moment=0;
        for(unsigned j=0;j<72;j++){
            int64_t d=(int64_t)s->filtered[(m-35+j)%4096]-s->filtered[(m-36+j)%4096],w=d*d;
            mass+=w;moment+=w*(-71+(int)j*2);
        }
        if(mass){int64_t mid=(2*(int64_t)m*mass+moment+mass)/(2*mass),adjusted=((mid-20)*25+9)/18;
            if(adjusted<0||adjusted>(int64_t)s->index)return -1;
            pos=(uint32_t)adjusted;}
    }
    if(s->count&&pos<=s->last_position)return -1;
    q.position=pos;q.rr_samples=s->count?pos-s->last_position:0;
    memset(q.rr,0,sizeof(q.rr));
    if(q.rr_samples){
        double local=0,global=0;unsigned ng=s->rr_count<400?s->rr_count:400,nl=ng<80?ng:80;
        for(unsigned j=0;j<ng;j++){uint32_t v=s->rr[(s->rr_head+s->rr_count-1-j)%401];global+=v;if(j<nl)local+=v;}
        local=nl?local/nl:q.rr_samples;global=ng?global/ng:q.rr_samples;
        double v[3]={q.rr_samples/local,q.rr_samples/global,local/global};
        for(unsigned j=0;j<3;j++)q.rr[j]=(float)fmin(4,fmax(0,v[j]))/4.f;
        if(s->rr_count==401){s->rr_head=(s->rr_head+1)%401;s->rr_count--;}
        s->rr[(s->rr_head+s->rr_count++)%401]=q.rr_samples;
    }
    s->last_position=pos;s->count++;s->pending[s->pending_count++]=q;return 0;
}
static int drain(InputStream*s,HgbRequest out[32],int finish){
    int n=0;
    while(s->pending_count){
        HgbRequest q=s->pending[0];uint32_t pos=q.position;
        if(!finish&&pos>=178&&(uint64_t)pos+266>s->index)break;
        memmove(s->pending,s->pending+1,(--s->pending_count)*sizeof(q));
        uint32_t ready=q.ready_at;
        int complete=pos>=178&&(uint64_t)pos+266<=s->index;
        if(complete&&ready<pos+266)ready=pos+266;
        if(ready<s->last_ready)ready=s->last_ready;
        if(ready>s->index)return -1;
        q.ready_at=ready;s->last_ready=ready;
        memset(q.waveform,0,sizeof(q.waveform));
        if(!complete){q.input_status=4;memset(q.rr,0,sizeof(q.rr));}
        else{
            if(s->index-(pos-178)>=4096)return -1;
            double sampled[129],values[128],sum=0,variance=0;
            for(int m=0;m<129;m++){
                double v=0;int t=m*125+1250;
                for(int k=0;k<445;k++){int h=t-k*36;if(h>=0&&h<=2500)v+=((double)s->raw[(pos-178+(unsigned)k)%4096]/4096.)*ecg_window500_fir[h];}
                sampled[m]=v;
            }
            for(unsigned m=0;m<128;m++){values[m]=sampled[m]+(sampled[m+1]-sampled[m])*(8./125.);sum+=values[m];}
            double mean=sum/128.;for(unsigned m=0;m<128;m++){values[m]-=mean;variance+=values[m]*values[m];}
            double std=sqrt(variance/128.);if(std<.05)std=.05;
            for(unsigned m=0;m<128;m++)q.waveform[m]=(float)(values[m]/std);
            q.input_status=q.beat_id==1?2:0;
        }
        out[n++]=q;
    }
    return n;
}
int cnn_input_stream_push(void*state,int16_t code,uint32_t index,HgbRequest out[32]){
    InputStream*s=state;if(!s||!out||s->closed||index!=s->index+1U)return -1;
    s->index=index;s->raw[index%4096]=code;
    int16_t value;uint32_t internal;int rc=ecg_rate500_push(&s->rate,code,index,&value,&internal);
    if(rc<0)return -2;
    if(rc){if(internal!=s->filtered_count)return -2;s->filtered[s->filtered_count++%4096]=value;}
    HgbRequest batch[32];int count=ecg_pipeline_push(pipeline(s),code,index,(EcgClassRequest*)batch);
    if(count<0)return -3;
    for(int i=0;i<count;i++)if(enqueue(s,batch+i))return -4;
    return drain(s,out,0);
}
int cnn_input_stream_finish(void*state,HgbRequest out[32]){
    InputStream*s=state;if(!s||!out||s->closed||s->index==UINT32_MAX)return -1;
    HgbRequest batch[32];int count=ecg_pipeline_finish(pipeline(s),(EcgClassRequest*)batch);
    if(count<0)return -2;
    for(int i=0;i<count;i++)if(enqueue(s,batch+i))return -3;
    s->closed=1;return drain(s,out,1);
}
