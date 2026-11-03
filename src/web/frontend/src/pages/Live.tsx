import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AnalysisTask, ApiError, downloadFile, post, request, uploadWithProgress } from '../services/api';
import Waveform from '../components/Waveform';
import BackLink from '../components/BackLink';
import { PlotPoint } from '../components/waveformGeometry';
import { sourceTrace, SourceSample, SourceTrace } from '../components/liveSource';
import { categoryFor, identifyCsv, hasFilteredResult, sourceSignal, sourceSignals, selectSourceTrace, defaultSourceTrace, LiveCategory, SourceSignal } from '../components/liveOptions';

interface Port {port: string; label: string; device_id: string;}
interface Ports {ports: Port[]; warnings: string[]; zynq: string; capture: string;}
interface Resources {device:string;stage:string;board_verified:boolean;note:string;capacity:Record<string,number>;rows:{name:string;scope:string;lut:number;ff:number;bram36:number;dsp:number}[];}
interface Sample {seq: number; index: number; raw: number; filt: number | null;}
interface Beat {seq: number; pos: number; index: number | null; rr: number | null; hr: number | null; cls: string; conf: number | null;
  algorithm_wait_ms?:number;arm_us?:number;pl_call_us?:number;host_after_ready_ms?:number;arm_class_id?:number;pl_class_id?:number;}
interface Result {header: {fs: number | null; scale: number | null; source: string; detector: string; caps: number; session: string} | null;
  samples: Sample[]; events: Beat[]; hr: number | null; rr_ms: number | null; cls: string; waveform_origin?: string;}
interface Session {owned?:boolean; board_model?:boolean; owner_username?:string; id: string; kind: string; created: number; active: boolean; info: Record<string, unknown>;
  capture_info: Record<string, unknown>; source_samples: SourceSample[]; result: Result; diagnostics: unknown;
  files: string[]; scope: string; source_unit: string; persistence_error: string | null; analysis?: {status:string; task_id:string|null; error:string|null}|null;}
const needsFile = new Set(['log', 'vendor_csv', 'bridge_csv', 'standard360', 'standard500']);
const needsBoard = new Set(['result_serial', 'bridge_csv', 'bridge_serial', 'standard360', 'standard500']);
const needsCapture = new Set(['vendor_serial', 'bridge_serial']);
const modelInputs = new Set(['vendor_csv', 'vendor_serial', 'bridge_csv', 'bridge_serial', 'standard500']);
const states: Record<string, string> = {starting:'准备中', connecting:'连接中', running:'运行中', waiting:'已打开串口 · 暂无新字节',
  draining:'停止来源 · 收尾中', closing:'关闭并保存中', stopped:'已停止 · 历史数据', error:'出错 · 已保留记录'};
const number = (value: unknown, digits = 0) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '未提供';

export default function Live() {
  const [search, setSearch] = useSearchParams();
  const id = search.get('session') ?? '';
  function setId(value: string) {setSearch({session: value});}
  const [kind, setKind] = useState('bridge_serial'), [ports, setPorts] = useState<Ports>({ports:[],warnings:[],zynq:'',capture:''});
  const category = categoryFor(kind);
  function selectKind(value: string) {setKind(value);setFile(null);setMessage('');setBoardModel(['standard500','bridge_csv','bridge_serial'].includes(value));}
  function selectCategory(value: LiveCategory) {selectKind({capture:'bridge_serial',file:'bridge_csv',demo:'demo',advanced:'result_serial'}[value]);}
  const [zynq, setZynq] = useState(''), [capture, setCapture] = useState('');
  const [file, setFile] = useState<File | null>(null), [limit, setLimit] = useState(5000), [seconds, setSeconds] = useState(10);
  const [realtime, setRealtime] = useState(true), [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  const [session, setSession] = useState<Session | null>(null);
  const [history, setHistory] = useState<Session[]>([]), [channel, setChannel] = useState('ecg'), [sourceMode, setSourceMode] = useState<SourceTrace>('display_mv');
  const [resultTrace, setResultTrace] = useState('raw');
  const [autoAnalyze, setAutoAnalyze] = useState(false), [standardPreprocess, setStandardPreprocess] = useState('');
  const [boardModel, setBoardModel] = useState(true);
  const [boardClassifier, setBoardClassifier] = useState('cnn');
  const [boardPrecision, setBoardPrecision] = useState('FP32');
  const [resources,setResources]=useState<Resources|null>(null);
  const [boardStreaming, setBoardStreaming] = useState(false);
  const [manualTask, setManualTask] = useState<{session: string; id: string} | null>(null);
  const lastRequest = useRef(0);
  async function chooseFile(selected: File | null) {
    setFile(selected);setMessage('');
    if (!selected || !['bridge_csv','standard360','standard500'].includes(kind)) return;
    setBusy(true);
    try {
      const detected=identifyCsv(await selected.slice(0,8192).text());
      setKind(detected);setBoardModel(detected!=='standard360');setStandardPreprocess('');
    } catch(error) {setFile(null);setMessage((error as Error).message);}
    finally {setBusy(false);}
  }
  async function refresh() {
    const data = await request<Ports>('/live/ports');
    setPorts(data);
    // 同COM身份变化时清除选择；后端启动前还会再次核对。
    setZynq(old => data.ports.some(p=>p.port===old && ports.ports.some(previous=>previous.port===old && previous.device_id===p.device_id)) ? old : data.zynq);
    setCapture(old => data.ports.some(p=>p.port===old && ports.ports.some(previous=>previous.port===old && previous.device_id===p.device_id)) ? old : data.capture);
  }
  async function loadHistory() {setHistory(await request<Session[]>('/live/sessions'));}
  useEffect(()=>{void refresh().catch(e=>setMessage(e.message)); void loadHistory().catch(e=>setMessage(e.message));},[]); // 只枚举，不打开串口
  useEffect(()=>{void request<Resources>('/live/accelerators').then(setResources).catch(()=>setResources(null));},[id]);
  useEffect(()=>{
    setSession(null);
    setMessage('');
    if (!id) return;
    let cancelled = false, timer: ReturnType<typeof setTimeout>;
    const generation = ++lastRequest.current;
    async function poll() {
      try {
        const data = await request<Session>(`/live/sessions/${id}`);
        if (cancelled || generation !== lastRequest.current) return;
        setSession(data);
        setKind(data.kind);
        setBoardModel(Boolean(data.board_model));
        if(data.info.classifier==='cnn'||data.info.classifier==='hgb')setBoardClassifier(String(data.info.classifier));
        setBoardStreaming(Boolean(data.info.streaming));
        setBoardPrecision(data.info.precision==='W8A8'?'W8A8':'FP32');
        if (data.active || data.analysis?.status === 'waiting') timer = setTimeout(()=>void poll(), 250);
        else {void loadHistory().catch(()=>{});}
      } catch (error) {
        if (!cancelled) {
          setMessage((error as Error).message);
          if (!(error instanceof ApiError && [401,403,404].includes(error.status))) timer=setTimeout(()=>void poll(),2000);
        }
      }
    }
    void poll();
    return ()=>{cancelled=true;clearTimeout(timer);};
  },[id]);
  async function start() {
    setBusy(true); setMessage('');
    try {
      if ((autoAnalyze || boardModel) && kind==='standard500' && !standardPreprocess) throw new Error('请先选择标准500Hz的预处理状态');
      if (boardModel && !['bridge_csv','bridge_serial','standard500'].includes(kind)) throw new Error('板端模型仅支持500Hz连续心电输入');
      let uploadId = '';
      if (needsFile.has(kind)) {
        if (!file) throw new Error('请先选择输入文件');
        const body = new FormData(); body.append('file',file);
        const uploaded = await uploadWithProgress<{id: string}>('/live/uploads',body);
        uploadId = uploaded.id;
      }
      const board = ports.ports.find(p=>p.port===zynq), source = ports.ports.find(p=>p.port===capture);
      const data = await post<{id: string}>('/live/sessions', {kind, upload_id:uploadId, seconds, sample_limit:limit, realtime,
        analyze_when_complete:autoAnalyze, board_model:boardModel, board_classifier:boardClassifier, board_precision:boardModel&&boardClassifier==='cnn'?boardPrecision:'FP32', board_streaming:boardModel&&boardClassifier==='cnn'&&boardStreaming, standard_preprocess:kind==='standard500' ? standardPreprocess || null : null,
        zynq_port:zynq, zynq_port_identity:board?.device_id ?? '', capture_port:capture, capture_port_identity:source?.device_id ?? ''});
      setSession(null); setId(data.id);
    } catch (error) {setMessage((error as Error).message);} finally {setBusy(false);}
  }
  async function stop() {
    if (!id) return;
    setBusy(true);
    try {setSession(await post<Session>(`/live/sessions/${id}/stop`)); await loadHistory();}
    catch(error) {setMessage((error as Error).message);} finally {setBusy(false);}
  }
  function save(path: string, name: string) {void downloadFile(path,name).catch(error=>setMessage(error.message));}
  async function analyzeSaved() {
    if (!session) return;
    setBusy(true); setMessage('');
    try {
      const task = await post<AnalysisTask>(`/live/sessions/${session.id}/analyze`,
        {standard_preprocess:session.kind==='standard500' ? standardPreprocess || null : null});
      setManualTask({session:session.id,id:task.id});
    } catch(error) {setMessage((error as Error).message);} finally {setBusy(false);}
  }
  const active = Boolean(session?.active);
  const analysisTaskId = manualTask && manualTask.session === session?.id ? manualTask.id : session?.analysis?.task_id;
  const result = session?.result, rate = result?.header?.fs ?? null;
  const filteredAvailable = hasFilteredResult(result?.header?.caps ?? 0, result?.samples ?? []);
  const effectiveResultTrace = filteredAvailable ? resultTrace : 'raw';
  const sourceSamples = session?.source_samples ?? [];
  const signalOptions = sourceSignals(sourceSamples,channel);
  const effectiveSourceMode = selectSourceTrace(sourceSamples,channel,sourceSignal(sourceMode),sourceMode==='mv'||sourceMode.endsWith('_mv'));
  const selectedSignal = sourceSignal(effectiveSourceMode);
  const voltageTrace = selectSourceTrace(sourceSamples,channel,selectedSignal,true);
  const codeTrace = selectSourceTrace(sourceSamples,channel,selectedSignal,false);
  const signalLabels = {original:'原始采集',vendor:'设备滤波',baseline:'去基线波形',display:'节律显示滤波',resp:'呼吸显示滤波'};
  const resultDivisor = rate ?? 1;
  const scale = result?.header?.scale;
  const secondary: PlotPoint[] = [];
  let previousFiltered: number | null = null;
  if (effectiveResultTrace==='both') for (const sample of result?.samples ?? []) {
    if (sample.filt===null) continue;
    secondary.push({t:sample.index/resultDivisor,v:scale?sample.filt/scale:sample.filt,
      breakBefore:previousFiltered!==null && sample.index!==previousFiltered+1});
    previousFiltered=sample.index;
  }
  const waveform: PlotPoint[] = [];
  let previousResult: number | null = null;
  for (const sample of result?.samples ?? []) {
    const value = effectiveResultTrace==='filt' ? sample.filt : sample.raw;
    if (value === null) continue;
    waveform.push({t:sample.index/resultDivisor, v:scale ? value/scale : value,
      breakBefore:previousResult!==null && sample.index!==previousResult+1});
    previousResult=sample.index;
  }
  const sourcePlot = sourceTrace(session?.source_samples ?? [], session?.kind ?? '', channel, effectiveSourceMode);
  const sourcePoints = sourcePlot.points, sourceRate = sourcePlot.fs;
  const span = (points: PlotPoint[], fs: number) => Math.max(1/fs,(points[points.length-1]?.t ?? 0)-(points[0]?.t ?? 0));
  const markers = (result?.events ?? []).filter(e=>e.index!==null).map(e=>({t:e.index!/resultDivisor,label:String(e.seq)}));
  const shownState = session ? states[String(session.info.state)] ?? String(session.info.state) : '未开始';
  const samples = session?.info.source_samples ?? session?.capture_info.total ?? session?.capture_info.samples;
  return <>
    {id && <div className="page-back"><BackLink label="返回记录" /></div>}
    <section className="edge-console"><div className="detail-head"><div><p className="eyebrow">ZYNQ-7020 · ECG EDGE ANALYSIS</p><h1>心电边缘检测</h1></div><span className={`badge ${session?.info.error?'badge-bad':active?'badge-ok':'badge-muted'}`}>{shownState}</span></div>
      <div className="signal-path" aria-label="处理链路"><span>ADS1292R<span>500 Hz · 单导联</span></span><b>→</b><span>Zynq ARM<span>高通 · R 峰 · 历史特征</span></span><b>→</b><span>FPGA PL<span>CNN / HGB 推理</span></span><b>→</b><span>结果与性能<span>逐拍核对 · 板上计时</span></span></div>
      {session?.owned===false && <p className="notice">{session.owner_username} 的共享测量 · 只读</p>}
      <fieldset className="live-configuration" disabled={session?.owned===false}><div className="live-controls">
        <label>使用方式<select value={category==='advanced'?'advanced':category} disabled={active || busy} onChange={e=>selectCategory(e.target.value as LiveCategory)}>
          <option value="capture">实时采集</option><option value="file">文件回放</option><option value="demo">演示</option>
          {category==='advanced' && <option value="advanced">高级工具</option>}
        </select></label>
        {category==='capture' && <label>处理方式<select value={kind} disabled={active || busy} onChange={e=>selectKind(e.target.value)}><option value="bridge_serial">板卡处理</option><option value="vendor_serial">采集回放</option></select></label>}
        {category==='file' && <label>处理方式<select value={kind==='vendor_csv'?'vendor_csv':'bridge_csv'} disabled={active || busy} onChange={e=>selectKind(e.target.value)}><option value="bridge_csv">CSV · 板卡处理（自动识别）</option><option value="vendor_csv">CSV · 回放（采集原码）</option></select></label>}
        {needsFile.has(kind) && <label>输入文件（≤32MiB）<input key={category+String(kind==='vendor_csv')} type="file" accept={kind==='log'?'.log':'.csv'} disabled={active || busy} onChange={e=>void chooseFile(e.target.files?.[0] ?? null)}/>{file && kind.startsWith('standard') && <small>{kind==='standard500'?'500':'360'} Hz · {kind==='standard360'?'板卡检测':'可选 CNN / HGB'}</small>}</label>}
        {needsBoard.has(kind) && <label>Zynq USB_UART<select value={zynq} disabled={active || busy} onChange={e=>{setZynq(e.target.value);if(e.target.value===capture)setCapture('');}}><option value="">请选择</option>{ports.ports.map(p=><option key={p.port} value={p.port}>{p.port} · {p.label}</option>)}</select></label>}
        {needsCapture.has(kind) && <label>采集USB接收器<select value={capture} disabled={active || busy} onChange={e=>setCapture(e.target.value)}><option value="">请选择</option>{ports.ports.filter(p=>p.port!==zynq || !needsBoard.has(kind)).map(p=><option key={p.port} value={p.port}>{p.port} · {p.label}</option>)}</select></label>}
        {kind==='demo' && <label>演示秒数<input type="number" min="1" max="300" value={seconds} disabled={active || busy} onChange={e=>setSeconds(Number(e.target.value))}/></label>}
        {needsCapture.has(kind) && <label>采集点数上限<input type="number" min="1" max="1800000" value={limit} disabled={active || busy} onChange={e=>setLimit(Number(e.target.value))}/></label>}
      </div>
      {['bridge_csv','bridge_serial','standard500'].includes(kind) && <label className="inline"><input type="checkbox" checked={boardModel} disabled={active || busy} onChange={e=>setBoardModel(e.target.checked)}/>板端心拍分类</label>}
      {boardModel && <div className="model-selector"><label>板端模型<select value={boardClassifier} disabled={active||busy} onChange={e=>setBoardClassifier(e.target.value)}><option value="cnn">CNN · H27 · N / S / V / F</option><option value="hgb">HGB · v92 · N / S / VF</option></select></label><p>{boardClassifier==='cnn'?'CNN 是神经网络，根据心拍波形识别 N、S、V、F 四类心拍。':'HGB 是树模型分类器，识别 N、S、VF 三类心拍。VF 为 V/E/F 合并类别。'}</p></div>}
      {boardModel&&boardClassifier==='cnn'&&<><div className="analysis-mode"><label htmlFor="cnn-precision">计算精度</label><select id="cnn-precision" value={boardPrecision} disabled={active||busy} onChange={e=>setBoardPrecision(e.target.value)}><option value="FP32">FP32 · 原版 CNN</option><option value="W8A8">INT8 · 量化 CNN 对比</option></select></div><div className="analysis-mode"><label htmlFor="analysis-mode">分析模式</label><select id="analysis-mode" value={boardStreaming?'stream':'batch'} disabled={active||busy} onChange={e=>setBoardStreaming(e.target.value==='stream')}><option value="batch">CNN 整段分析</option><option value="stream">CNN 实时分析 · 边采边测</option></select></div></>}
      {kind==='standard500' && <label>输入预处理<select value={standardPreprocess} disabled={active||busy} onChange={e=>setStandardPreprocess(e.target.value)}><option value="">请选择输入状态</option><option value="hp05">未滤波 mV → 板端 0.5 Hz 高通</option><option value="raw">已匹配因果高通 → 直接输入</option></select></label>}
      <details className="live-advanced" open={category==='advanced' || undefined}><summary>高级工具</summary><div className="actions">
        <button className="secondary" disabled={active || busy} onClick={()=>selectKind('result_serial')}>仅接收板卡结果</button>
        <button className="secondary" disabled={active || busy} onClick={()=>selectKind('log')}>原始日志回放</button>
      </div>{category==='advanced' && <p className="hint">当前：{kind==='log'?'原始日志回放':'仅接收板卡结果'}。可从“使用方式”返回采集、文件或演示。</p>}</details>
      <div className="actions"><button disabled={active || busy} onClick={()=>void start()}>开始并记录</button><button className="secondary" disabled={!active || busy} onClick={()=>void stop()}>停止并保存</button>
        <button className="secondary" disabled={active || busy} onClick={()=>void refresh().catch(error=>setMessage(error.message))}>刷新端口</button>
        {(needsFile.has(kind) || kind==='demo') && <label className="inline"><input type="checkbox" checked={realtime} disabled={active || busy} onChange={e=>setRealtime(e.target.checked)}/>按采样节拍回放</label>}</div>
      </fieldset>{ports.warnings.map((warning,index)=><p className="hint" key={index}>{warning}</p>)}
      <p role="status" className={message || session?.info.error || session?.persistence_error?'notice notice-error':'hint'}>{message || String(session?.info.error || session?.persistence_error || (session?'':'选择输入与模型，开始一次测量。'))}</p>
      <div className="stat-grid"><div><span>心率（次/分）</span><strong>{number(result?.hr,1)}</strong></div><div><span>RR（ms）</span><strong>{number(result?.rr_ms,1)}</strong></div><div><span>心拍类别</span><strong>{result?.cls ?? '未提供'}</strong></div><div><span>累计来源点数</span><strong>{number(samples)}</strong></div></div>
      {session?.kind==='demo' && <p className="notice">合成波形，事件是预设标记。它们不代表算法检测或分类结果。</p>}
      {session?.kind!=='demo' && result?.header?.source==='SYNTH' && <p className="notice">来源声明为合成波形；事件含义以会话头的检测器和能力标志为准，不能作为真实人体输入证据。</p>}
    </section>
    {session?.owned!==false && <details className="host-analysis"><summary>电脑端 HGB 对照分析</summary><section><h2>电脑端 HGB</h2>
      <label className="inline"><input type="checkbox" checked={autoAnalyze} disabled={active || busy} onChange={e=>setAutoAnalyze(e.target.checked)}/>采集结束后自动分析完整记录</label>
      {(kind==='standard500' || session?.kind==='standard500') && <label>标准500Hz预处理<select value={standardPreprocess} disabled={active || busy} onChange={e=>setStandardPreprocess(e.target.value)}><option value="">请选择，不猜测处理状态</option><option value="hp05">未额外滤波 → 模型hp05</option><option value="raw">已匹配因果高通 → 模型raw</option></select></label>}
      <p className="hint">电脑端HGB研究模型，使用完整保存记录；不读取设备或网页显示滤波结果。不代表板端分类、最终合格模型或临床诊断。</p>
      {session?.analysis?.status==='waiting' && <p role="status">正在关闭文件并提交分析…</p>}
      {session?.analysis?.error && <p className="notice notice-error">{session.analysis.error}</p>}
      {session && modelInputs.has(session.kind) && <button disabled={active || busy || session.analysis?.status==='waiting'} onClick={()=>void analyzeSaved()}>分析已保存记录</button>}
      {analysisTaskId && <Link className="button" state={{returnTo:'/live?session='+id}} to={'/analyze?task='+analysisTaskId}>查看模型分析</Link>}
    </section></details>}
    {session && <section><div className="record-toolbar"><h2>波形与事件{!active?' · 历史数据':''}</h2><button className="secondary" disabled={session?.owned===false} onClick={()=>save(`/live/sessions/${id}/svg`,'ecg.svg')}>导出结果SVG</button></div>
      {session.info.state==='waiting' && <p className="notice">暂无新串口字节，数值为上次接收值；这不等于物理断连。</p>}
      {session.source_samples.length>0 && <><div className="wave-toolbar"><strong>来源</strong>{!session.kind.startsWith('standard') && <select value={channel} onChange={e=>{setChannel(e.target.value);setSourceMode(defaultSourceTrace(e.target.value));}}><option value="ecg">CH2 · ECG</option><option value="resp">CH1 · 呼吸</option></select>}
        {!session.kind.startsWith('standard') && <><label className="inline">信号<select aria-label="来源信号" value={selectedSignal} onChange={e=>setSourceMode(selectSourceTrace(sourceSamples,channel,e.target.value as SourceSignal,true))}>{signalOptions.map(signal=><option key={signal} value={signal}>{signalLabels[signal]}</option>)}</select></label>
          {voltageTrace!==codeTrace && <label className="inline">单位<select aria-label="来源单位" value={effectiveSourceMode} onChange={e=>setSourceMode(e.target.value as SourceTrace)}><option value={voltageTrace}>mV（标称）</option><option value={codeTrace}>ADC码值</option></select></label>}</>}</div>
        <Waveform points={sourcePoints} offset={sourcePoints[0]?.t ?? 0} duration={span(sourcePoints,sourceRate)} unit={sourcePlot.unit}/>
        {effectiveSourceMode==='mv' && !session.kind.startsWith('standard') && <p className="hint">标称电压尚未实测标定，保留直流；与送板前去直流、量化后的波形幅值可能不同。</p>}
        {selectedSignal==='resp' && <p className="hint">PC因果呼吸显示滤波：0.05Hz高通和0.8Hz低通，存在相位延迟，开始约10秒为过渡；保留原码，不计算呼吸率。</p>}
        </>}
      {session.board_model && Boolean(session.info.class_counts) && <div className="beat-counts" aria-label="心拍分类统计">{Object.entries(session.info.class_counts as Record<string,number>).map(([label,count])=><div className={label==='UNCLASSIFIED'?'beat-count unclassified':'beat-count'} key={label}><div className="beat-count-main"><span className="beat-class">{label==='UNCLASSIFIED'?'未分类':label}</span><strong>{count}<small>拍</small></strong></div><span className="beat-description">{beatDescriptions[label]??label}</span></div>)}</div>}
      {session.board_model && session.info.execution_location==='zynq_pl' && <FpgaPerformance info={session.info}/>}
      {session.board_model&&session.info.classifier==='cnn'&&<ResourcePanel resources={resources}/>}
      <div className="wave-toolbar"><strong>{result?.waveform_origin==='host_input'?'送板输入（非板端波形回显）':needsBoard.has(session.kind)?'板卡返回':'日志/演示'}</strong>{filteredAvailable ? <select aria-label="板卡波形" value={effectiveResultTrace} onChange={e=>setResultTrace(e.target.value)}><option value="raw">输入波形</option><option value="filt">板端滤波</option><option value="both">输入与滤波叠加</option></select> : <span>输入波形</span>}<span>{result?.header?.detector ?? '尚无合法会话头'}</span></div>
      <Waveform points={waveform} secondary={secondary} offset={waveform[0]?.t ?? 0} duration={span(waveform,resultDivisor)} axisUnit={rate?'s':'样本号'} unit={scale?'mV（声明比例）':'码值（未标定）'} markers={markers}/>
      <div className="live-table"><table><thead><tr>{['事件号','源位置（样本号）','RR（点）','心率','类别','模型概率',...(session.info.streaming?['ARM输出','FPGA输出','算法等待 ms','ARM µs','FPGA含传输 µs','收样至结果 ms']:[])].map(title=><th key={title}>{title}</th>)}</tr></thead><tbody>{[...(result?.events ?? [])].reverse().map(event=><tr key={event.seq}><td>{event.seq}</td><td>{event.pos}{event.index===null?'（不在当前可见窗口）':''}</td><td>{event.rr ?? '未知'}</td><td>{number(event.hr,1)}</td><td>{result?.header && (result.header.caps & 16) ? event.cls==='?'?'未知':event.cls : '未提供'}</td><td>{event.conf!==null?`${number(event.conf*100,1)}%`:'—'}</td>{Boolean(session.info.streaming)&&<><td>{event.arm_class_id!==undefined?['N','S','V','F'][event.arm_class_id]??'未分类':'—'}</td><td>{event.pl_class_id!==undefined?['N','S','V','F'][event.pl_class_id]??'未分类':'—'}</td><td>{number(event.algorithm_wait_ms,1)}</td><td>{number(event.arm_us,2)}</td><td>{number(event.pl_call_us,2)}</td><td>{number(event.host_after_ready_ms,1)}</td></>}</tr>)}</tbody></table></div>
      <details><summary>诊断与保存文件</summary><pre className="mono-wrap">{JSON.stringify({session:id,info:session.info,capture:session.capture_info,diagnostics:session.diagnostics},null,2)}</pre>
        <div className="actions">{session.files.map(name=><button key={name} className="secondary" disabled={active} onClick={()=>save(`/live/sessions/${id}/files/${name}`,name.substring(name.lastIndexOf('/')+1))}>{name}</button>)}</div>
      </details><p className="hint">页面离开、刷新或网络中断不会停止服务端记录；回到本页选择会话后可继续查看、停止。显示缓存最多4096点、256个事件；完整记录在下载文件中。</p>
    </section>}
    <section><h2>测量记录</h2><p>所有测量和分析版本统一保存在历史记录中。</p><Link className="button secondary" to="/records">查看历史记录</Link>
      {history.filter(row=>row.active && row.id!==id).map(row=><p key={row.id}><Link className="button secondary" to={'/live?session='+row.id}>继续查看进行中的测量</Link></p>)}
    </section>
  </>;
}

function FpgaPerformance({info}:{info:Record<string,unknown>}) {
  const p=info.performance as Record<string,unknown>|null;
  if(!p)return <p>尚无本次FPGA性能数据。</p>;
  const cnn=info.classifier==='cnn';
  const latest=info.latest_performance as Record<string,unknown>|undefined;
  const quantized=info.precision==='W8A8';
  return <><section className="accelerator-panel" aria-label="FPGA分类性能"><div className="detail-head"><div><p className="eyebrow">ON-BOARD BENCHMARK · {cnn?(quantized?'CNN INT8 / W8A8':'CNN FP32'):'HGB Q40'}</p><h3>ARM / FPGA 加速对比</h3></div><span className="badge badge-ok">{number(p.mismatches)} 拍不一致</span></div>

    <div className="stat-grid">
      <div><span>ARM分类 · µs/拍</span><strong>{number(p.arm_mean_us,2)}</strong></div>
      <div><span>{cnn?'FPGA计算等待':'FPGA核心'} · µs/拍</span><strong>{number(p.pl_core_mean_us,2)}</strong></div>
      <div><span>FPGA含传输 · µs/拍</span><strong>{number(p.pl_call_mean_us,2)}</strong></div>
      <div className="speedup-metric"><span>累计含传输加速比</span><strong>{number(p.call_speedup,4)} 倍</strong></div>
    </div>
    <p className="comparison-summary">已对比 <strong>{number(p.beats)}</strong> 拍 · 超出容差或类别不一致 <strong>{number(p.mismatches)}</strong> 拍 · 累计计算阶段加速 <strong>{number(p.core_speedup,4)} 倍</strong></p>
    {Boolean(info.streaming)&&<><div className="stat-grid"><div><span>累计 ARM 网络时间 · ms</span><strong>{number(Number(p.arm_ticks)/Number(p.timer_hz)*1000,3)}</strong></div><div><span>累计 FPGA 含传输 · ms</span><strong>{number(Number(p.pl_call_ticks)/Number(p.timer_hz)*1000,3)}</strong></div><div><span>最近有效一拍含传输加速比</span><strong>{number(latest?.call_speedup,4)} 倍</strong></div><div><span>待送队列 · 点</span><strong>{number(info.queue_depth)}</strong></div></div><p className="hint">每拍更新，累计加速比 = ARM 总时间 ÷ FPGA 调用总时间。固定网络运算量接近，比值可能保持稳定。每拍依次运行 ARM 和 FPGA；含传输指板内寄存器传输，不含串口。算法等待及收样至结果延迟见逐拍表；电脑 CPU 尚未计时。</p></>}
    {Number(p.arm_mean_us)>0 && <div className="latency-bars"><div><span>ARM</span><i style={{width:'100%'}}/><b>{number(p.arm_mean_us,2)} µs</b></div><div><span>FPGA</span><i style={{width:`${Math.min(100,100*Number(p.pl_call_mean_us)/Number(p.arm_mean_us))}%`}}/><b>{number(p.pl_call_mean_us,2)} µs</b></div></div>}<p className="hint">{cnn?'同一Zynq、相同模型与所选精度的网络。ARM负责信号预处理与历史特征；PL执行卷积、残差、池化及全连接。计算等待由ARM轮询计时，包含启动及轮询误差。':'同一Zynq、相同Q40分类树；ARM负责预处理与特征，PL执行树分类。'} 比较不含前后处理和串口；含传输指寄存器写入与读回。数值来自本次板端计数。</p>
  </section>{quantized&&<QuantizationPanel info={info}/>}</>;
}


const beatDescriptions:Record<string,string>={N:'正常类心拍',S:'室上性异位心拍',V:'室性异位心拍',F:'正常与室性融合拍',VF:'室性 / 逸搏 / 融合拍',UNCLASSIFIED:'心拍不完整或信息不足'};

function QuantizationPanel({info}:{info:Record<string,unknown>}) {
  const q=info.quantization_comparison as Record<string,unknown>|undefined;
  const p=info.performance as Record<string,unknown>|undefined;
  // P/Q分开发送；只有同一批次的累计计时才绘制，避免新旧拍数混用。
  if(!q||!p||q.beats!==p.beats||Number(q.beats)<=0)return null;
  return <section className="quant-panel" aria-label="量化同拍实时对比">
    <div className="benchmark-heading"><div><span className="panel-kicker">精度对比</span><h3>FP32 → INT8 · 同拍对比</h3></div><span className="measurement-tag">{info.streaming?'逐拍累计':'本次累计'} · {number(q.beats)} 拍</span></div>
    <div className="quant-lanes">{(['arm','pl'] as const).map(key=>{
      const before=Number(q[`fp32_${key}_mean_us`]),after=Number(q[`int8_${key}_mean_us`]);
      const speed=q[key==='arm'?'quantization_arm_speedup':'quantization_pl_speedup'];
      return <article className="quant-lane" key={key}><div className="quant-lane-title"><h4>{key==='arm'?'Zynq ARM':'Zynq FPGA'}</h4><span>平均每拍 · ms</span></div>
        <div className="precision-reading"><span>FP32</span><strong>{number(before/1000,3)}</strong><div className="precision-track"><i style={{width:'100%'}}/></div></div>
        <div className="precision-reading int8"><span>INT8</span><strong>{number(after/1000,3)}</strong><div className="precision-track"><i style={{width:`${Math.min(100,after/before*100)}%`}}/></div></div>
        <div className="quant-gain"><span>量化前 / 量化后</span><strong>{number(speed,3)}<small> 倍</small></strong></div></article>;
    })}</div>
    <div className="benchmark-footer"><span>量化前后类别变化 <b>{number(q.class_changes)}</b> 拍</span><span>FPGA 时间含板内寄存器传输</span></div>
  </section>;
}

function ResourcePanel({resources}:{resources:Resources|null}) {
  return <section className="resource-panel" aria-label="FPGA资源占用"><div className="benchmark-heading"><div><span className="panel-kicker">硬件资源</span><h3>FPGA 资源占用 · Zynq-7020</h3></div><span className="measurement-tag static">Vivado · 实现报告</span></div>
    {resources?.stage==='routed'?<div className="resource-cards">{resources.rows.map(row=><article className="resource-card" key={row.name}><h4>{row.name}</h4><div className="resource-meters">{(['lut','ff','bram36','dsp'] as const).map(k=>{
      const percent=row[k]/resources.capacity[k]*100;
      return <div className="resource-meter" key={k}><div><span>{k==='bram36'?'BRAM':k.toUpperCase()}</span><strong>{number(percent,1)}<small>%</small></strong></div><div className="resource-track"><i style={{width:`${percent}%`}}/></div><span className="resource-capacity">{number(row[k],k==='bram36'?1:0)} / {number(resources.capacity[k])}{k==='bram36'?' 块':''}</span></div>;
    })}</div></article>)}</div>:<p className="resource-empty">资源报告待生成</p>}
  </section>;
}
