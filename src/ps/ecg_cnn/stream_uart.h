/* main.c私有串口扩展；复用严格CRC/确认，不影响整段接口。 */
#ifdef ECG_CNN_PL
static CnnHistory live_history;
static uint64_t live_input_ticks,live_prepare_ticks,live_classify_ticks;
static uint32_t live_events;
extern int32_t cnn_last_arm_class,cnn_last_pl_class;
static int stream_performance(uint32_t sid){
    int rc=tx("P,%u,%s,%u,%u,%llu,%llu,%llu,%llu,100000000\n",sid,
#ifdef ECG_CNN_INT8
        cnn_int8_mode?"W8A8":"FP32",
#else
        "FP32",
#endif
        cnn_pl_beats,cnn_pl_mismatches,
        (unsigned long long)cnn_arm_ticks,(unsigned long long)cnn_pl_call_ticks,
        (unsigned long long)cnn_pl_core_ticks,(unsigned long long)frequency);
#ifdef ECG_CNN_INT8
    if(!rc&&cnn_int8_mode)return quant_performance(sid);
#endif
    return rc;
}
static int stream_emit(uint32_t sid,HgbRequest*r,int count,uint32_t received){
    for(int i=0;i<count;i++){
        uint64_t a=cnn_arm_ticks,b=cnn_pl_call_ticks,c=cnn_pl_core_ticks;CnnResult result;
#ifdef ECG_CNN_INT8
        uint64_t fa=cnn_fp32_arm_ticks,fp=cnn_fp32_call_ticks;
#endif
        XTime begin=now();
        if(cnn_history_push(&live_history,r+i,&result)){tx("F,%u,STREAM_CLASSIFY\n",sid);return -1;}
        uint64_t elapsed=now()-begin;live_classify_ticks+=elapsed;
        uint64_t arm=cnn_arm_ticks-a,call=cnn_pl_call_ticks-b,core=cnn_pl_core_ticks-c;
        uint64_t network=arm+call;
#ifdef ECG_CNN_INT8
        network+=cnn_fp32_arm_ticks-fa+cnn_fp32_call_ticks-fp;
#endif
        uint64_t feature=elapsed>=network?elapsed-network:0;
        int arm_class=result.status?-1:cnn_last_arm_class,pl_class=result.status?-1:cnn_last_pl_class;
        if(tx("T,%u,%u,%u,%llu,%llu,%llu,%llu,%d,%d\n",sid,result.beat_id,received,
            (unsigned long long)arm,(unsigned long long)call,(unsigned long long)core,(unsigned long long)feature,
            arm_class,pl_class))return -1;
        uint32_t p[4];memcpy(p,result.probability,sizeof(p));
        if(tx("R,%u,%u,%u,%u,%u,%d,%08x,%08x,%08x,%08x\n",sid,result.beat_id,result.position,result.ready_at,
            result.status,result.class_id,p[0],p[1],p[2],p[3]))return -1;
        live_events++;
    }
    return 0;
}
static int stream_session(char *v[8],unsigned nf){
    uint32_t sid,limit,fs;
    if(nf!=7||strcmp(v[0],"I")||strcmp(v[1],"CNN-STREAM-1")||number(v[2],10,&sid)||!sid||
       number(v[3],10,&fs)||fs!=500||strcmp(v[4],"mV")||(strcmp(v[5],"hp05")&&strcmp(v[5],"raw"))||
       number(v[6],10,&limit)||!limit||limit>1800000){tx("F,0,BAD_STREAM_HEADER\n");return -1;}
    if(cnn_input_stream_size()>sizeof(workspace.data)||cnn_input_stream_init(workspace.data))return -1;
    cnn_history_init(&live_history);cnn_pl_clear();live_events=0;live_input_ticks=live_prepare_ticks=live_classify_ticks=0;
    HgbInput input={0};int hp=!strcmp(v[5],"hp05");uint32_t index=0;
    tx("H,CNN-STREAM-1,READY,500,mV,16d56a6b1065df35f3e11c4cc285055b421978bd451d5da1b72df8f1744fcfc7\n");
    if(tx("A,%u,READY,32\n",sid))return -1;
    for(;;){
        char text[192],*f[8];uint32_t got,start,n,crc;
        if(line(text,10000000)){tx("F,%u,STREAM_INPUT_TIMEOUT_OR_UART\n",sid);return -1;}
        unsigned fields_count=fields(text,f);
        if(fields_count==2&&!strcmp(f[0],"X")&&!number(f[1],10,&got)&&got==sid){tx("S,%u,CANCEL\n",sid);return 0;}
        if(fields_count==3&&!strcmp(f[0],"D")&&!number(f[1],10,&got)&&got==sid&&!number(f[2],10,&n)&&n==index&&index){
            HgbRequest batch[32];XTime begin=now();int count=cnn_input_stream_finish(workspace.data,batch);
            live_prepare_ticks+=now()-begin;
            if(count<0||stream_emit(sid,batch,count,index-1)){tx("F,%u,STREAM_FINISH\n",sid);return -1;}
            if(stream_performance(sid))return -1;
            return tx("D,%u,%u,%u,%u,%llu,%llu,%llu\n",sid,index,live_events,input.clipped,
                (unsigned long long)(live_input_ticks*1000000ULL/frequency),
                (unsigned long long)(live_prepare_ticks*1000000ULL/frequency),
                (unsigned long long)(live_classify_ticks*1000000ULL/frequency));
        }
        if(fields_count!=5||strcmp(f[0],"B")||number(f[1],10,&got)||got!=sid||number(f[2],10,&start)||start!=index||
           number(f[3],10,&n)||!n||n>32||n>limit-index||number(f[4],16,&crc)){tx("F,%u,BAD_STREAM_BLOCK\n",sid);return -1;}
        union {double align;unsigned char bytes[256];} block;
        if(rx(block.bytes,n*8,10000000)||crc32(block.bytes,n*8)!=crc){tx("F,%u,STREAM_CRC_OR_UART\n",sid);return -1;}
        double mv[32];int16_t converted[32];memcpy(mv,block.bytes,n*8);XTime begin=now();
        if(ecg_hgb_input(&input,mv,n,hp,converted)){tx("F,%u,INVALID_MV\n",sid);return -1;}
        live_input_ticks+=now()-begin;uint32_t previous_beats=cnn_pl_beats;
        for(unsigned k=0;k<n;k++){
            HgbRequest batch[32];begin=now();int count=cnn_input_stream_push(workspace.data,converted[k],index,batch);
            live_prepare_ticks+=now()-begin;
            if(count<0||stream_emit(sid,batch,count,index)){tx("F,%u,STREAM_PROCESS\n",sid);return -1;}
            index++;
        }
        if(cnn_pl_beats!=previous_beats&&stream_performance(sid))return -1;
        if(tx("A,%u,NEXT,%u\n",sid,index))return -1;
    }
}
#endif
