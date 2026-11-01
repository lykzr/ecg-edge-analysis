import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AnalysisTask, ApiError, downloadFile, post, request, uploadWithProgress } from '../services/api';
import Waveform from '../components/Waveform';
import BackLink from '../components/BackLink';
import { PlotPoint } from '../components/waveformGeometry';
import { sourceTrace, SourceSample, SourceTrace } from '../components/liveSource';
import { categoryFor, hasFilteredResult, sourceSignal, sourceSignals, selectSourceTrace, defaultSourceTrace, LiveCategory, SourceSignal } from '../components/liveOptions';

interface Port {port: string; label: string; device_id: string;}
interface Ports {ports: Port[]; warnings: string[]; zynq: string; capture: string;}
interface Sample {seq: number; index: number; raw: number; filt: number | null;}
interface Beat {seq: number; pos: number; index: number | null; rr: number | null; hr: number | null; cls: string; conf: number | null;}
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
  const [history, setHistory] = useState<Session[]>([]), [channel, setChannel] = useState('ecg'), [sourceMode, setSourceMode] = useState<SourceTrace>('mv');
  const [resultTrace, setResultTrace] = useState('raw');
  const [autoAnalyze, setAutoAnalyze] = useState(true), [standardPreprocess, setStandardPreprocess] = useState('');
  const [boardModel, setBoardModel] = useState(true);
  const [manualTask, setManualTask] = useState<{session: string; id: string} | null>(null);
  const lastRequest = useRef(0);
  async function refresh() {
    const data = await request<Ports>('/live/ports');
    setPorts(data);
    // 同COM身份变化时清除选择；后端启动前还会再次核对。
    setZynq(old => data.ports.some(p=>p.port===old && ports.ports.some(previous=>previous.port===old && previous.device_id===p.device_id)) ? old : data.zynq);
    setCapture(old => data.ports.some(p=>p.port===old && ports.ports.some(previous=>previous.port===old && previous.device_id===p.device_id)) ? old : data.capture);
  }
  async function loadHistory() {setHistory(await request<Session[]>('/live/sessions'));}
  useEffect(()=>{void refresh().catch(e=>setMessage(e.message)); void loadHistory().catch(e=>setMessage(e.message));},[]); // 只枚举，不打开串口
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
      if (boardModel && !['bridge_csv','bridge_serial','standard500'].includes(kind)) throw new Error('板端模型仅支持500Hz标准或厂商送样');
      let uploadId = '';
      if (needsFile.has(kind)) {
        if (!file) throw new Error('请先选择输入文件');
        const body = new FormData(); body.append('file',file);
        const uploaded = await uploadWithProgress<{id: string}>('/live/uploads',body);
        uploadId = uploaded.id;
      }
      const board = ports.ports.find(p=>p.port===zynq), source = ports.ports.find(p=>p.port===capture);
      const data = await post<{id: string}>('/live/sessions', {kind, upload_id:uploadId, seconds, sample_limit:limit, realtime,
        analyze_when_complete:autoAnalyze, board_model:boardModel, standard_preprocess:kind==='standard500' ? standardPreprocess || null : null,
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
  const signalLabels = {original:'原始采集',vendor:'厂商滤波',baseline:'基线校正',display:'节律显示滤波',resp:'呼吸显示滤波'};
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
    <section><div className="detail-head"><div><p className="eyebrow">采集 · 中转 · 保存</p><h1>实时与板卡</h1></div><span className={`badge ${session?.info.error?'badge-bad':active?'badge-ok':'badge-muted'}`}>{shownState}</span></div>
      <p>电脑接收采集数据，Zynq处理后返回结果。演示与日志可离线运行；实时QRS由板端运行；完整记录保存后可另交电脑端研究模型分析。</p>
      {session?.owned===false && <p className="notice">{session.owner_username} 的共享测量 · 只读</p>}
      <fieldset className="live-configuration" disabled={session?.owned===false}><div className="live-controls">
        <label>使用方式<select value={category==='advanced'?'advanced':category} disabled={active || busy} onChange={e=>selectCategory(e.target.value as LiveCategory)}>
          <option value="capture">实时采集</option><option value="file">文件回放</option><option value="demo">演示</option>
          {category==='advanced' && <option value="advanced">高级工具</option>}
        </select></label>
        {category==='capture' && <label>处理方式<select value={kind} disabled={active || busy} onChange={e=>selectKind(e.target.value)}><option value="bridge_serial">板卡处理</option><option value="vendor_serial">仅查看采集</option></select></label>}
        {category==='file' && <label>文件格式与处理<select value={kind} disabled={active || busy} onChange={e=>selectKind(e.target.value)}><option value="bridge_csv">厂商CSV · 板卡处理（500Hz）</option><option value="vendor_csv">厂商CSV · 仅查看</option><option value="standard500">标准CSV · 板卡处理（500Hz）</option><option value="standard360">标准CSV · 板卡处理（360Hz）</option></select></label>}
        {needsFile.has(kind) && <label>输入文件（≤32MiB）<input key={kind} type="file" accept={kind==='log'?'.log':'.csv'} disabled={active || busy} onChange={e=>setFile(e.target.files?.[0] ?? null)}/></label>}
        {needsBoard.has(kind) && <label>Zynq USB_UART<select value={zynq} disabled={active || busy} onChange={e=>{setZynq(e.target.value);if(e.target.value===capture)setCapture('');}}><option value="">请选择</option>{ports.ports.map(p=><option key={p.port} value={p.port}>{p.port} · {p.label}</option>)}</select></label>}
        {needsCapture.has(kind) && <label>采集USB接收器<select value={capture} disabled={active || busy} onChange={e=>setCapture(e.target.value)}><option value="">请选择</option>{ports.ports.filter(p=>p.port!==zynq || !needsBoard.has(kind)).map(p=><option key={p.port} value={p.port}>{p.port} · {p.label}</option>)}</select></label>}
        {kind==='demo' && <label>演示秒数<input type="number" min="1" max="300" value={seconds} disabled={active || busy} onChange={e=>setSeconds(Number(e.target.value))}/></label>}
        {needsCapture.has(kind) && <label>采集点数上限<input type="number" min="1" max="1800000" value={limit} disabled={active || busy} onChange={e=>setLimit(Number(e.target.value))}/></label>}
      </div>
      {['bridge_csv','bridge_serial','standard500'].includes(kind) && <label className="inline"><input type="checkbox" checked={boardModel} disabled={active || busy} onChange={e=>setBoardModel(e.target.checked)}/>Zynq ARM整段分类（最多30000点，保存完整输入后分类）</label>}
      {boardModel && <p className="notice">板端HGB v92/fold0研究模型，结果在整段收样后返回；非连续实时分类、非FPGA PL推理。N/S/VF中VF是V/E/F合并，不表示心室颤动。原实时心率模式请取消此项。</p>}
      <details className="live-advanced" open={category==='advanced' || undefined}><summary>高级工具</summary><div className="actions">
        <button className="secondary" disabled={active || busy} onClick={()=>selectKind('result_serial')}>仅接收板卡结果</button>
        <button className="secondary" disabled={active || busy} onClick={()=>selectKind('log')}>原始日志回放</button>
      </div>{category==='advanced' && <p className="hint">当前：{kind==='log'?'原始日志回放':'仅接收板卡结果'}。可从“使用方式”返回采集、文件或演示。</p>}</details>
      <div className="actions"><button disabled={active || busy} onClick={()=>void start()}>开始并记录</button><button className="secondary" disabled={!active || busy} onClick={()=>void stop()}>停止并保存</button>
        <button className="secondary" disabled={active || busy} onClick={()=>void refresh().catch(error=>setMessage(error.message))}>刷新端口</button>
        {(needsFile.has(kind) || kind==='demo') && <label className="inline"><input type="checkbox" checked={realtime} disabled={active || busy} onChange={e=>setRealtime(e.target.checked)}/>按采样节拍回放</label>}</div>
      {category==='file' && <p className="hint">厂商CSV含ecg_raw；标准CSV须为index,sample,fs,scale，比例4096单位/mV。请选择与文件及板端程序匹配的格式。</p>}
      </fieldset>{ports.warnings.map((warning,index)=><p className="hint" key={index}>{warning}</p>)}
      <p role="status" className={message || session?.info.error || session?.persistence_error?'notice notice-error':'hint'}>{message || String(session?.info.error || session?.persistence_error || session?.scope || '就绪；每次运行建立新目录，不覆盖旧记录。')}</p>
      <div className="stat-grid"><div><span>心率（次/分）</span><strong>{number(result?.hr,1)}</strong></div><div><span>RR（ms）</span><strong>{number(result?.rr_ms,1)}</strong></div><div><span>心拍类别</span><strong>{result?.cls ?? '未提供'}</strong></div><div><span>累计来源点数</span><strong>{number(samples)}</strong></div></div>
      {session?.kind==='demo' && <p className="notice">合成波形，事件是预设标记。它们不代表算法检测或分类结果。</p>}
      {session?.kind!=='demo' && result?.header?.source==='SYNTH' && <p className="notice">来源声明为合成波形；事件含义以会话头的检测器和能力标志为准，不能作为真实人体输入证据。</p>}
    </section>
    {session?.owned!==false && <section><h2>电脑端模型分析</h2>
      <label className="inline"><input type="checkbox" checked={autoAnalyze} disabled={active || busy} onChange={e=>setAutoAnalyze(e.target.checked)}/>采集结束后自动分析完整记录</label>
      {(kind==='standard500' || session?.kind==='standard500') && <label>标准500Hz预处理<select value={standardPreprocess} disabled={active || busy} onChange={e=>setStandardPreprocess(e.target.value)}><option value="">请选择，不猜测处理状态</option><option value="hp05">未额外滤波 → 模型hp05</option><option value="raw">已匹配因果高通 → 模型raw</option></select></label>}
      <p className="hint">电脑端HGB研究模型，使用完整保存记录；不读取厂商或网页显示滤波结果。不代表板端分类、最终合格模型或临床诊断。</p>
      {session?.analysis?.status==='waiting' && <p role="status">正在关闭文件并提交分析…</p>}
      {session?.analysis?.error && <p className="notice notice-error">{session.analysis.error}</p>}
      {session && modelInputs.has(session.kind) && <button disabled={active || busy || session.analysis?.status==='waiting'} onClick={()=>void analyzeSaved()}>分析已保存记录</button>}
      {analysisTaskId && <Link className="button" state={{returnTo:'/live?session='+id}} to={'/analyze?task='+analysisTaskId}>查看模型分析</Link>}
    </section>}
    {session && <section><div className="record-toolbar"><h2>波形与事件{!active?' · 历史数据':''}</h2><button className="secondary" disabled={session?.owned===false} onClick={()=>save(`/live/sessions/${id}/svg`,'ecg.svg')}>导出结果SVG</button></div>
      {session.info.state==='waiting' && <p className="notice">暂无新串口字节，数值为上次接收值；这不等于物理断连。</p>}
      {session.source_samples.length>0 && <><div className="wave-toolbar"><strong>来源</strong>{!session.kind.startsWith('standard') && <select value={channel} onChange={e=>{setChannel(e.target.value);setSourceMode(defaultSourceTrace(e.target.value));}}><option value="ecg">CH2 · ECG</option><option value="resp">CH1 · 呼吸</option></select>}
        {!session.kind.startsWith('standard') && <><label className="inline">信号<select aria-label="来源信号" value={selectedSignal} onChange={e=>setSourceMode(selectSourceTrace(sourceSamples,channel,e.target.value as SourceSignal,true))}>{signalOptions.map(signal=><option key={signal} value={signal}>{signalLabels[signal]}</option>)}</select></label>
          {voltageTrace!==codeTrace && <label className="inline">单位<select aria-label="来源单位" value={effectiveSourceMode} onChange={e=>setSourceMode(e.target.value as SourceTrace)}><option value={voltageTrace}>mV（标称）</option><option value={codeTrace}>ADC码值</option></select></label>}</>}</div>
        <Waveform points={sourcePoints} offset={sourcePoints[0]?.t ?? 0} duration={span(sourcePoints,sourceRate)} unit={sourcePlot.unit}/>
        {effectiveSourceMode==='mv' && !session.kind.startsWith('standard') && <p className="hint">标称电压尚未实测标定，保留直流；与送板前去直流、量化后的波形幅值可能不同。</p>}
        {selectedSignal==='resp' && <p className="hint">PC因果呼吸显示滤波：0.05Hz高通和0.8Hz低通，存在相位延迟，开始约10秒为过渡；保留原码，不计算呼吸率。</p>}
        {(selectedSignal==='baseline'||selectedSignal==='display') && <p className="hint">PC基线校正为0.5Hz因果高通；节律显示另加40Hz低通和50Hz陷波，开始约5秒为过渡。不用于ST测量，不按典型幅值缩放，不改变Zynq或模型输入。</p>}</>}
      {session.board_model && <p className="notice">分类来源：Zynq ARM · {String(session.info.model_sha256 ?? '')} · 研究模型未全部达标。事件是模型自身检测/重切拍位置，未套用其他QRS事件编号。</p>}
      <div className="wave-toolbar"><strong>{result?.waveform_origin==='host_input'?'送板输入（非板端波形回显）':needsBoard.has(session.kind)?'板卡返回':'日志/演示'}</strong>{filteredAvailable ? <select aria-label="板卡波形" value={effectiveResultTrace} onChange={e=>setResultTrace(e.target.value)}><option value="raw">输入波形</option><option value="filt">板端滤波</option><option value="both">输入与滤波叠加</option></select> : <span>输入波形</span>}<span>{result?.header?.detector ?? '尚无合法会话头'}</span></div>
      <Waveform points={waveform} secondary={secondary} offset={waveform[0]?.t ?? 0} duration={span(waveform,resultDivisor)} axisUnit={rate?'s':'样本号'} unit={scale?'mV（声明比例）':'码值（未标定）'} markers={markers}/>
      <div className="live-table"><table><thead><tr>{['事件号','源位置（样本号）','RR（点）','心率','类别'].map(title=><th key={title}>{title}</th>)}</tr></thead><tbody>{[...(result?.events ?? [])].reverse().map(event=><tr key={event.seq}><td>{event.seq}</td><td>{event.pos}{event.index===null?'（不在当前可见窗口）':''}</td><td>{event.rr ?? '未知'}</td><td>{number(event.hr,1)}</td><td>{result?.header && (result.header.caps & 16) ? event.cls==='?'?'未知':event.cls : '未提供'}</td></tr>)}</tbody></table></div>
      <details><summary>诊断与保存文件</summary><pre className="mono-wrap">{JSON.stringify({session:id,info:session.info,capture:session.capture_info,diagnostics:session.diagnostics},null,2)}</pre>
        <div className="actions">{session.files.map(name=><button key={name} className="secondary" disabled={active} onClick={()=>save(`/live/sessions/${id}/files/${name}`,name.substring(name.lastIndexOf('/')+1))}>{name}</button>)}</div>
      </details><p className="hint">页面离开、刷新或网络中断不会停止服务端记录；回到本页选择会话后可继续查看、停止。显示缓存最多4096点、256个事件；完整记录在下载文件中。</p>
    </section>}
    <section><h2>测量记录</h2><p>所有测量和分析版本统一保存在历史记录中。</p><Link className="button secondary" to="/records">查看历史记录</Link>
      {history.filter(row=>row.active && row.id!==id).map(row=><p key={row.id}><Link className="button secondary" to={'/live?session='+row.id}>继续查看进行中的测量</Link></p>)}
    </section>
  </>;
}
