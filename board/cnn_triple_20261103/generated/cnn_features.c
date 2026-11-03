/* H27因果形态122项，与冻结Python实现逐值核对。 */
#include "cnn.h"
#include "stream.h"
#include <math.h>
#include <string.h>
static double clip(double x,double lo,double hi){return x<lo?lo:x>hi?hi:x;}
static double mean(const double *x,unsigned n){double s=0;for(unsigned i=0;i<n;i++)s+=x[i];return n?s/n:0;}
static double median(double *x,unsigned n){for(unsigned i=1;i<n;i++){double v=x[i];unsigned j=i;while(j&&x[j-1]>v){x[j]=x[j-1];j--;}x[j]=v;}return n? n%2?x[n/2]:(x[n/2-1]+x[n/2])/2:0;}
static unsigned peak(const float *x){unsigned p=44;for(unsigned j=45;j<60;j++)if(fabs(x[j])>fabs(x[p]))p=j;return p;}
static void align(const float *x,double z[128]){double sign=x[peak(x)]<0?-1:1;for(unsigned j=0;j<128;j++)z[j]=x[j]*sign;}
static double energy(const double *x,unsigned n){double s=0;for(unsigned i=0;i<n;i++)s+=x[i]*x[i];return s/n;}
static double cosine(const double*z,const double*b,unsigned lo,unsigned hi){double a=0,c=0,d=0;for(unsigned j=lo;j<hi;j++){a+=z[j]*b[j];c+=z[j]*z[j];d+=b[j]*b[j];}return a/fmax(sqrt(c*d),1e-8);}
static void morphology(const HgbRequest*r,const float bg[128],unsigned count,float f[122]){
    double z[128],b[128],d[128];align(r->waveform,z);
    for(unsigned j=0;j<128;j++){b[j]=bg[j];d[j]=z[j]-b[j];}
    unsigned k=0;for(unsigned j=0;j<3;j++)f[k++]=r->rr[j];
    for(unsigned j=0;j<32;j++)f[k++]=(float)mean(z+4*j,4);
    for(unsigned j=0;j<16;j++)f[k++]=(float)(mean(z+8*j,4)-mean(z+8*j+4,4));
    const unsigned ranges[4][2]={{8,40},{40,66},{66,104},{104,128}};
    for(unsigned a=0;a<4;a++){
        unsigned lo=ranges[a][0],hi=ranges[a][1];double min=z[lo],max=z[lo],var=0;
        for(unsigned j=lo;j<hi;j++){if(z[j]<min)min=z[j];if(z[j]>max)max=z[j];if(j>lo)var+=fabs(z[j]-z[j-1]);}
        f[k++]=(float)mean(z+lo,hi-lo);f[k++]=(float)min;f[k++]=(float)max;
        f[k++]=(float)energy(z+lo,hi-lo);f[k++]=(float)(var/(hi-lo-1));
    }
    double amplitude=0,min=z[0],max=z[0];unsigned width=0;
    for(unsigned j=40;j<66;j++)amplitude=fmax(amplitude,fabs(z[j]));
    for(unsigned j=40;j<66;j++)if(fabs(z[j])>=.5*amplitude)width++;
    for(unsigned j=0;j<128;j++){min=fmin(min,z[j]);max=fmax(max,z[j]);}
    f[k++]=(float)(width/144.);f[k++]=(float)((peak(r->waveform)-51.2)/144.);f[k++]=(float)(max-min);
    for(unsigned j=0;j<32;j++)f[k++]=(float)mean(d+4*j,4);
    for(unsigned a=0;a<4;a++){
        unsigned lo=ranges[a][0],hi=ranges[a][1];double absmean=0;
        for(unsigned j=lo;j<hi;j++)absmean+=fabs(d[j]);
        f[k++]=(float)(absmean/(hi-lo));f[k++]=(float)mean(d+lo,hi-lo);f[k++]=(float)energy(d+lo,hi-lo);
    }
    f[k++]=(float)cosine(z,b,0,128);f[k++]=(float)cosine(z,b,40,66);f[k++]=(float)(count/8.);
    f[k++]=count?(float)clip(energy(z+40,26)/fmax(energy(b+40,26),1e-4),0,8):0;
}

int cnn_record(const HgbRequest*r,unsigned n,CnnResult*out){
    if(n>480 || (n && (!r||!out)))return -1;
    unsigned released=0,ids[8],have=0;
    for(unsigned i=0;i<n;i++){
        if(r[i].beat_id!=i+1 || r[i].sampling_hz!=500 || r[i].position>r[i].ready_at || (i && (r[i].position<=r[i-1].position || r[i].ready_at<r[i-1].ready_at)) || (!i && !r[i].input_status) || (r[i].input_status!=0 && r[i].input_status!=2 && r[i].input_status!=4))return -1;
        CnnResult*o=&out[i];memset(o,0,sizeof(*o));o->beat_id=r[i].beat_id;o->position=r[i].position;o->ready_at=r[i].ready_at;o->status=r[i].input_status;o->class_id=-1;
        for(unsigned k=0;k<4;k++)o->logits[k]=o->probability[k]=NAN;
        while(released<i && r[released].ready_at<=r[i].position){
            if(r[released].input_status!=4){if(have==8){memmove(ids,ids+1,7*sizeof(*ids));have--;}ids[have++]=released;}
            released++;
        }
        o->history_count=have;
        if(o->status)continue;
        float bg[128]={0},hand[122],history[8]={0};
        for(unsigned k=0;k<128 && have;k++){
            double values[8];for(unsigned j=0;j<have;j++){const float*x=r[ids[j]].waveform;values[j]=(double)x[k]*(x[peak(x)]<0?-1:1);}
            bg[k]=(float)median(values,have);
        }
        morphology(&r[i],bg,have,hand);
        double intervals[32];unsigned lo=i>32?i-32:1,num=0;
        for(unsigned j=lo;j<i;j++)intervals[num++]=r[j].position-r[j-1].position;
        double med=num?median(intervals,num):r[i].position-r[i-1].position;
        unsigned first=i>7?i-7:1,used=i-first+1;
        for(unsigned j=first;j<=i;j++)history[8-used+j-first]=(float)(clip((r[j].position-r[j-1].position)/med,0,4)/4);
        if(cnn_forward(r[i].waveform,r[i].rr,hand,history,o->logits))return -2;
        o->class_id=0;float max=o->logits[0],sum=0;
        for(unsigned k=1;k<4;k++)if(o->logits[k]>max){max=o->logits[k];o->class_id=k;}
        for(unsigned k=0;k<4;k++){o->probability[k]=expf(o->logits[k]-max);sum+=o->probability[k];}
        for(unsigned k=0;k<4;k++)o->probability[k]/=sum;
    }
    return 0;
}

void cnn_history_init(CnnHistory*s){if(s)memset(s,0,sizeof(*s));}
int cnn_history_push(CnnHistory*s,const HgbRequest*r,CnnResult*o){
    if(!s||!r||!o||r->beat_id!=s->last_id+1||r->sampling_hz!=500||r->position>r->ready_at||
       (s->last_id&&(r->position<=s->last_position||r->ready_at<s->last_ready))||
       (!s->last_id&&!r->input_status)||(r->input_status!=0&&r->input_status!=2&&r->input_status!=4))return -1;
    while(s->pending_count&&s->pending_ready[0]<=r->position){
        if(s->backgrounds==8){memmove(s->background,s->background+1,7*sizeof(s->background[0]));s->backgrounds--;}
        memcpy(s->background[s->backgrounds++],s->pending_wave[0],sizeof(s->background[0]));
        s->pending_count--;memmove(s->pending_wave,s->pending_wave+1,s->pending_count*sizeof(s->pending_wave[0]));
        memmove(s->pending_ready,s->pending_ready+1,s->pending_count*sizeof(s->pending_ready[0]));
    }
    memset(o,0,sizeof(*o));o->beat_id=r->beat_id;o->position=r->position;o->ready_at=r->ready_at;
    o->status=r->input_status;o->history_count=s->backgrounds;o->class_id=-1;
    for(unsigned k=0;k<4;k++)o->logits[k]=o->probability[k]=NAN;
    if(!o->status){
        if(!s->position_count)return -1;
        float bg[128]={0},hand[122],history[8]={0};
        for(unsigned k=0;k<128&&s->backgrounds;k++){
            double values[8];for(unsigned j=0;j<s->backgrounds;j++)values[j]=s->background[j][k];bg[k]=(float)median(values,s->backgrounds);
        }
        morphology(r,bg,s->backgrounds,hand);
        double intervals[32];unsigned num=s->position_count-1;
        for(unsigned j=0;j<num;j++)intervals[j]=s->positions[j+1]-s->positions[j];
        double med=num?median(intervals,num):r->position-s->last_position;
        unsigned used=s->position_count<8?s->position_count:8,first=s->position_count-used;
        for(unsigned j=0;j<used;j++){
            uint32_t next=first+j+1<s->position_count?s->positions[first+j+1]:r->position;
            history[8-used+j]=(float)(clip((next-s->positions[first+j])/med,0,4)/4);
        }
        if(cnn_forward(r->waveform,r->rr,hand,history,o->logits))return -2;
        o->class_id=0;float max=o->logits[0],sum=0;
        for(unsigned k=1;k<4;k++)if(o->logits[k]>max){max=o->logits[k];o->class_id=k;}
        for(unsigned k=0;k<4;k++){o->probability[k]=expf(o->logits[k]-max);sum+=o->probability[k];}
        for(unsigned k=0;k<4;k++)o->probability[k]/=sum;
    }
    if(r->input_status!=4){
        if(s->pending_count==32)return -3;
        double aligned[128];align(r->waveform,aligned);
        for(unsigned k=0;k<128;k++)s->pending_wave[s->pending_count][k]=(float)aligned[k];
        s->pending_ready[s->pending_count++]=r->ready_at;
    }
    if(s->position_count==33){memmove(s->positions,s->positions+1,32*sizeof(uint32_t));s->position_count--;}
    s->positions[s->position_count++]=r->position;s->last_position=r->position;s->last_ready=r->ready_at;s->last_id=r->beat_id;
    return 0;
}
