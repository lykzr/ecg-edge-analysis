#include "hgb.h"
#include <math.h>
#include <string.h>
static double clip(double x,double lo,double hi){return x<lo?lo:x>hi?hi:x;}
static double mean(const double *x,unsigned n){double s=0;for(unsigned i=0;i<n;i++)s+=x[i];return n?s/n:0;}
static double median(double *x,unsigned n){for(unsigned i=1;i<n;i++){double v=x[i];unsigned j=i;while(j&&x[j-1]>v){x[j]=x[j-1];j--;}x[j]=v;}return n? n%2?x[n/2]:(x[n/2-1]+x[n/2])/2:0;}
static unsigned peak(const float *x){unsigned p=44;for(unsigned j=45;j<60;j++)if(fabs(x[j])>fabs(x[p]))p=j;return p;}
static void align(const float *x,double z[128]){double sign=x[peak(x)]<0?-1:1;for(unsigned j=0;j<128;j++)z[j]=x[j]*sign;}
static double energy(const double *x,unsigned n){double s=0;for(unsigned i=0;i<n;i++)s+=x[i]*x[i];return s/n;}
static double cosine(const double*z,const double*b,unsigned lo,unsigned hi){double a=0,c=0,d=0;for(unsigned j=lo;j<hi;j++){a+=z[j]*b[j];c+=z[j]*z[j];d+=b[j]*b[j];}return a/fmax(sqrt(c*d),1e-8);}
static void bands(const double x[128],double out[12]){
    double low[128],next[128];memcpy(low,x,sizeof(low));unsigned k=0;
    const unsigned ranges[3][2]={{16,40},{40,80},{80,120}};
    for(unsigned distance=1;distance<=8;distance*=2){
        for(unsigned j=0;j<128;j++)next[j]=(low[j]+low[j<distance?0:j-distance])/2;
        for(unsigned r=0;r<3;r++){double s=0;for(unsigned j=ranges[r][0];j<ranges[r][1];j++)s+=fabs((low[j]-low[j<distance?0:j-distance])/2);out[k++]=s/(ranges[r][1]-ranges[r][0]);}
        memcpy(low,next,sizeof(low));
    }
}
/* 159维：相对形态122 + 当前RR1 + 频带36。 */
static void morphology(const HgbRequest*r,const float bg[128],unsigned count,float f[192]){
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
    f[k++]=(float)(clip(r->rr_samples/500.,0,4)/4);
    /* band_features使用原始极性的波形，与相对形态的对齐波形不同。 */
    double raw[128],current[12],past[12];for(unsigned j=0;j<128;j++)raw[j]=r->waveform[j];
    bands(raw,current);bands(b,past);
    for(unsigned j=0;j<12;j++)f[k++]=(float)current[j];
    for(unsigned j=0;j<12;j++)f[k++]=(float)past[j];
    for(unsigned j=0;j<12;j++)f[k++]=count?(float)clip(current[j]/fmax(past[j],.01),0,8):0;
}
static double ratio(double a,double b,double limit){return b>0?clip(a/b,0,limit)/limit:0;}
static double interval(const HgbRequest*r,size_t i){return i?(double)(r[i].position-r[i-1].position):0;}
static void rhythm(const HgbRequest*r,size_t i,float*f){
    if(!i){memset(f,0,12*sizeof(*f));return;}
    double cur=interval(r,i),m[2],med[2],sd[2],rm[2];unsigned cnt[2];const unsigned sizes[2]={8,32};
    for(unsigned t=0;t<2;t++){
        double a[32],sum=0,ss=0,delta=0;unsigned n=(i-1)<sizes[t]?(unsigned)(i-1):sizes[t];cnt[t]=n;
        for(unsigned j=0;j<n;j++){a[j]=interval(r,i-n+j);sum+=a[j];if(j)delta+=(a[j]-a[j-1])*(a[j]-a[j-1]);}
        m[t]=n?sum/n:cur;for(unsigned j=0;j<n;j++)ss+=(a[j]-m[t])*(a[j]-m[t]);
        sd[t]=n?sqrt(ss/n):0;rm[t]=n>1?sqrt(delta/(n-1)):0;med[t]=n?median(a,n):cur;
    }
    double prev=cnt[1]?interval(r,i-1):cur,lag=cnt[1]>=2?interval(r,i-2):cur;
    double values[12]={ratio(cur,prev,4),ratio(prev,med[0],4),ratio(cur,med[0],4),ratio(cur,med[1],4),ratio(sd[0],m[0],2),ratio(sd[1],m[1],2),ratio(rm[0],m[0],2),ratio(rm[1],m[1],2),ratio(fabs(cur-lag),med[0],4),(cur-prev)/(cur+prev),ratio(m[0],m[1],4),cnt[1]/32.};
    for(unsigned j=0;j<12;j++)f[j]=(float)values[j];
}
static void hermite(const HgbRequest*r,const float bg[128],unsigned count,float*f){
    double z[128],a[37],b[37],ac[6]={0},dc[6]={0};align(r->waveform,z);
    double zp=mean(z+28,8),zt=mean(z+73,8),bp=0,bt=0;
    for(unsigned j=28;j<36;j++)bp+=bg[j]/8.;
    for(unsigned j=73;j<81;j++)bt+=bg[j]/8.;
    double ae=0,be=0,de=0,ace=0,dce=0;
    for(unsigned j=0;j<37;j++){
        double fraction=(j+33-31.5)/45.;a[j]=z[j+33]-(zp*(1-fraction)+zt*fraction);b[j]=bg[j+33]-(bp*(1-fraction)+bt*fraction);
        double d=a[j]-b[j];ae+=a[j]*a[j];be+=b[j]*b[j];de+=d*d;
        for(unsigned c=0;c<6;c++){ac[c]+=a[j]*hgb_hermite_basis[j][c];dc[c]+=d*hgb_hermite_basis[j][c];}
    }
    for(unsigned c=0;c<6;c++){f[c]=(float)(ac[c]/sqrt(ae+1e-8));f[c+6]=count?(float)(dc[c]/sqrt(ae+be+1e-8)):0;ace+=ac[c]*ac[c];dce+=dc[c]*dc[c];}
    f[12]=(float)(fmax(ae-ace,0)/(ae+1e-8));f[13]=count?(float)(fmax(de-dce,0)/(ae+be+1e-8)):0;
}
int ecg_hgb_record(const HgbRequest*r,size_t n,uint32_t samples,HgbResult*out){
    if(!samples||samples>1800000||n>ECG_HGB_MAX_EVENTS||(n&&(!r||!out)))return -1;
    uint32_t gen=n?r[0].generation:0;
    for(size_t i=0;i<n;i++){
        if(!gen||r[i].generation!=gen||r[i].beat_id!=i+1||r[i].sampling_hz!=500||r[i].position>r[i].ready_at||r[i].ready_at>=samples||(i&&(r[i].position<=r[i-1].position||r[i].ready_at<r[i-1].ready_at))||r[i].rr_samples!=(uint32_t)interval(r,i))return -1;
        unsigned expected=r[i].position<178||(uint64_t)r[i].position+266>=samples?4:i?0:2;
        if(r[i].input_status!=expected||(!expected&&(uint64_t)r[i].position+266>r[i].ready_at))return -1;
        for(unsigned j=0;j<128;j++)if(!isfinite(r[i].waveform[j]))return -1;
        for(unsigned j=0;j<3;j++)if(!isfinite(r[i].rr[j]))return -1;
    }
    size_t released=0,ids[8];unsigned have=0;
    for(size_t i=0;i<n;i++){
        HgbResult*o=&out[i];memset(o,0,sizeof(*o));o->beat_id=r[i].beat_id;o->position=r[i].position;o->status=r[i].input_status;o->class_id=-1;
        o->decision_at=r[i].ready_at;for(unsigned c=0;c<3;c++)o->probability[c]=NAN;
        /* 只用当前R之前已报告的最后8个完整窗；首拍RR未知但完整窗仍可成为背景。 */
        while(released<i&&r[released].ready_at<=r[i].position){
            if(r[released].input_status!=4){
                if(have==8){memmove(ids,ids+1,7*sizeof(*ids));have--;}
                ids[have++]=released;
            }
            released++;
        }
        o->history_count=have;float bg[128]={0};
        for(unsigned k=0;k<128&&have;k++){
            double a[8];for(unsigned j=0;j<have;j++){const float*x=r[ids[j]].waveform;a[j]=(double)x[k]*(x[peak(x)]<0?-1:1);}bg[k]=(float)median(a,have);
        }
        if(!o->status){
            morphology(&r[i],bg,have,o->features);
            uint32_t deadline=(uint64_t)r[i].position+1250<samples?r[i].position+1250:samples-1;
            int available=i+1<n&&r[i+1].position-r[i].position<=1250&&r[i+1].ready_at<=deadline;
            o->decision_at=r[i].ready_at>(available?r[i+1].ready_at:deadline)?r[i].ready_at:available?r[i+1].ready_at:deadline;
            if(available){
                double pre=interval(r,i),next=interval(r,i+1),local=0,longmean=0;
                unsigned nl=i-1<80?(unsigned)(i-1):80,ng=i-1<400?(unsigned)(i-1):400;
                for(unsigned j=0;j<ng;j++)longmean+=interval(r,i-ng+j);
                for(unsigned j=0;j<nl;j++)local+=interval(r,i-nl+j);
                local=nl?local/nl:pre;longmean=ng?longmean/ng:pre;
                double v[7]={clip(next/500.,0,4)/4,ratio(next,pre,8),ratio(next,local,4),ratio(next,longmean,4),ratio(pre+next,2*local,4),(next-pre)/(next+pre),1};
                for(unsigned j=0;j<7;j++)o->features[159+j]=(float)v[j];
            }
            hermite(&r[i],bg,have,o->features+178);
        }
        /* 冻结Python路径对无效拍也保留12维节律；其余为零，绝不分类。 */
        rhythm(r,i,o->features+166);
        if(!o->status){if(ecg_hgb_probability(o->features,o->probability))return -2;o->class_id=0;for(unsigned c=1;c<3;c++)if(o->probability[c]>o->probability[o->class_id])o->class_id=(int32_t)c;}
    }
    return 0;
}
