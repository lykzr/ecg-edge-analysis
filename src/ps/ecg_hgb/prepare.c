/* 复用model/inference/native冻结检测器；不修改板上既有QRS或串口程序。 */
#include "hgb.h"
#include "pipeline.h"
#include "rate500.h"
#include "window500.h"
#include <math.h>
#include <string.h>
_Static_assert(sizeof(HgbRequest)==sizeof(EcgClassRequest),"请求布局不符");
static size_t offset(void){return (ecg_pipeline_size()+7U)&~(size_t)7U;}
size_t ecg_hgb_workspace_size(uint32_t samples){
    if(!samples||samples>1800000)return 0;
    return offset()+2*((size_t)(samples-1)*18/25+1);
}
int ecg_hgb_input(HgbInput*s,const double*x,size_t n,int highpass,int16_t*out){
    if(!s||(n&&(!x||!out))||(highpass!=0&&highpass!=1)||(s->started&&s->highpass!=(uint32_t)highpass))return -1;
    for(size_t i=0;i<n;i++)if(!isfinite(x[i]))return -1;
    /* 与原lfilter([a,-a],[1,-a],x,zi=[-a*x0])采用相同求值顺序。 */
    const double a=500/(500+2*3.14159265358979323846264338327950288*.5);
    for(size_t i=0;i<n;i++){
        double v=x[i];
        if(highpass){
            double zi=s->started?(-a*s->previous_input+a*s->previous_output):-a*v;
            v=a*x[i]+zi;
        }
        if(!isfinite(v))return -1;
        s->previous_input=x[i];s->previous_output=v;s->started=1;s->highpass=(uint32_t)highpass;
        double scaled=v*4096.;double rounded=copysign(floor(fabs(scaled)+.5),scaled);
        if(rounded>32767){rounded=32767;s->clipped++;}
        if(rounded< -32768){rounded=-32768;s->clipped++;}
        out[i]=(int16_t)rounded;
    }
    return 0;
}
int ecg_hgb_prepare(const int16_t*codes,uint32_t samples,HgbRequest*r,uint32_t cap,void*work,size_t bytes,uint32_t*events){
    size_t need=ecg_hgb_workspace_size(samples);
    if(!codes||!r||!events||!need||!work||((uintptr_t)work&7U)||bytes<need||!cap||cap>ECG_HGB_MAX_EVENTS)return -1;
    *events=0;EcgPipeline*p=work;const float zero[3]={0},one[3]={1,1,1};
    if(ecg_pipeline_init(p,1,zero,one))return -2;
    EcgClassRequest batch[32];uint32_t used=0;
    int16_t*filtered=(int16_t*)((unsigned char*)work+offset());
    EcgRate500 rate;ecg_rate500_init(&rate);uint32_t length=0;
    for(uint32_t i=0;i<samples;i++){
        int16_t value;uint32_t index;int rc=ecg_rate500_push(&rate,codes[i],i,&value,&index);
        if(rc<0)return -2;
        if(rc){if(index!=length)return -2;filtered[length++]=value;}
        int n=ecg_pipeline_push(p,codes[i],i,batch);
        if(n<0)return -2;
        if((uint64_t)used+(unsigned)n>cap)return -3;
        memcpy(r+used,batch,(size_t)n*sizeof(*r));used+=(unsigned)n;
    }
    int n=ecg_pipeline_finish(p,batch);if(n<0)return -2;
    if((uint64_t)used+(unsigned)n>cap)return -3;
    memcpy(r+used,batch,(size_t)n*sizeof(*r));used+=(unsigned)n;
    uint32_t lastready=0;
    for(uint32_t i=0;i<used;i++){
        uint32_t pos=r[i].position,m=(uint32_t)(((uint64_t)pos*18+12)/25+20);
        if(m>=36&&(uint64_t)m+36<length&&((uint64_t)(m+36)*25+17)/18<=r[i].ready_at){
            int64_t mass=0,moment=0;
            for(unsigned j=0;j<72;j++){
                int64_t d=(int64_t)filtered[m-35+j]-filtered[m-36+j],weight=d*d;
                mass+=weight;moment+=weight*(-71+(int)j*2);
            }
            if(mass){
                int64_t mid=(2*(int64_t)m*mass+moment+mass)/(2*mass);
                int64_t adjusted=((mid-20)*25+9)/18;
                if(adjusted<0||adjusted>=(int64_t)samples)return -4;
                pos=(uint32_t)adjusted;
            }
        }
        if(i&&pos<=r[i-1].position)return -4;
        r[i].position=pos;
        uint32_t ready=r[i].ready_at;
        int complete=pos>=178&&(uint64_t)pos+266<samples;
        if(complete&&ready<pos+266)ready=pos+266;
        if(ready<lastready)ready=lastready;
        if(ready>=samples)return -4;
        lastready=ready;r[i].ready_at=ready;
    }
    for(uint32_t i=0;i<used;i++){
        HgbRequest*q=&r[i];uint32_t pos=q->position;
        q->rr_samples=i?pos-r[i-1].position:0;
        memset(q->waveform,0,sizeof(q->waveform));memset(q->rr,0,sizeof(q->rr));
        unsigned ng=i?(i>400?400:i-1U):0,nl=i?(i>80?80:i-1U):0;
        if(q->rr_samples){
            double local=0,global=0;
            for(unsigned j=0;j<ng;j++)global+=r[i-1-j].rr_samples;
            for(unsigned j=0;j<nl;j++)local+=r[i-1-j].rr_samples;
            local=nl?local/nl:q->rr_samples;global=ng?global/ng:q->rr_samples;
            double v[3]={q->rr_samples/local,q->rr_samples/global,local/global};
            for(unsigned j=0;j<3;j++){if(v[j]<0)v[j]=0;if(v[j]>4)v[j]=4;q->rr[j]=(float)v[j]/4.f;}
        }
        int complete=pos>=178&&(uint64_t)pos+266<samples;
        if(!complete){q->input_status=4;memset(q->rr,0,sizeof(q->rr));continue;}
        if(pos+266>q->ready_at||q->ready_at-(pos-178)>=4096)return -4;
        double sampled[129],values[128],sum=0,variance=0;
        for(int m=0;m<129;m++){
            double v=0;int t=m*125+1250;
            for(int k=0;k<445;k++){int h=t-k*36;if(h>=0&&h<=2500)v+=((double)codes[pos-178+(unsigned)k]/4096.)*ecg_window500_fir[h];}
            sampled[m]=v;
        }
        for(unsigned m=0;m<128;m++){values[m]=sampled[m]+(sampled[m+1]-sampled[m])*(8./125.);sum+=values[m];}
        double mean=sum/128.;for(unsigned m=0;m<128;m++){values[m]-=mean;variance+=values[m]*values[m];}
        double std=sqrt(variance/128.);if(std<.05)std=.05;
        for(unsigned m=0;m<128;m++)q->waveform[m]=(float)(values[m]/std);
        q->input_status=i?0:2;
    }
    *events=used;return 0;
}
