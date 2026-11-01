import { useEffect, useRef, useState } from 'react';
import { downloadFile, post, request, uploadWithProgress } from '../services/api';
import Waveform from '../components/Waveform';
import { PlotPoint } from '../components/waveformGeometry';
import { sourceTrace, SourceSample, SourceTrace } from '../components/liveSource';

interface Port {port: string; label: string; device_id: string;}
interface Ports {ports: Port[]; warnings: string[]; zynq: string; capture: string;}
interface Sample {seq: number; index: number; raw: number; filt: number | null;}
interface Beat {seq: number; pos: number; index: number | null; rr: number | null; hr: number | null; cls: string; conf: number | null;}
interface Result {header: {fs: number | null; scale: number | null; source: string; detector: string; caps: number; session: string} | null;
  samples: Sample[]; events: Beat[]; hr: number | null; rr_ms: number | null; cls: string;}
interface Session {id: string; kind: string; created: number; active: boolean; info: Record<string, unknown>;
  capture_info: Record<string, unknown>; source_samples: SourceSample[]; result: Result; diagnostics: unknown;
  files: string[]; scope: string; source_unit: string; persistence_error: string | null;}
const modes = [
  ['demo', '合成演示（预设标记）'], ['log', '日志回放（raw.log）'],
  ['result_serial', '只接收Zynq结果'], ['vendor_csv', '厂商CSV · 查看采集'],
  ['vendor_serial', '蓝牙采集 · 查看原码'], ['bridge_csv', '厂商500Hz CSV → Zynq'],
  ['bridge_serial', '蓝牙采集 → Zynq'], ['standard360', '标准360Hz CSV → Zynq'], ['standard500', '标准500Hz CSV → Zynq'],
];
const needsFile = new Set(['log', 'vendor_csv', 'bridge_csv', 'standard360', 'standard500']);
const needsBoard = new Set(['result_serial', 'bridge_csv', 'bridge_serial', 'standard360', 'standard500']);
const needsCapture = new Set(['vendor_serial', 'bridge_serial']);
const states: Record<string, string> = {starting:'准备中', connecting:'连接中', running:'运行中', waiting:'已打开串口 · 暂无新字节',
  draining:'停止来源 · 收尾中', closing:'关闭并保存中', stopped:'已停止 · 历史数据', error:'出错 · 已保留记录'};
const number = (value: unknown, digits = 0) => typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '未提供';

export default function Live() {
  const [kind, setKind] = useState('demo'), [ports, setPorts] = useState<Ports>({ports:[],warnings:[],zynq:'',capture:''});
  const [zynq, setZynq] = useState(''), [capture, setCapture] = useState('');
  const [file, setFile] = useState<File | null>(null), [limit, setLimit] = useState(5000), [seconds, setSeconds] = useState(10);
  const [realtime, setRealtime] = useState(true), [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  const [session, setSession] = useState<Session | null>(null), [id, setId] = useState('');
  const [history, setHistory] = useState<Session[]>([]), [channel, setChannel] = useState('ecg'), [sourceMode, setSourceMode] = useState<SourceTrace>('code');
  const [resultTrace, setResultTrace] = useState('raw');
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
    if (!id) return;
    let cancelled = false, timer: ReturnType<typeof setTimeout>;
    const generation = ++lastRequest.current;
    async function poll() {
      try {
        const data = await request<Session>(`/live/sessions/${id}`);
        if (cancelled || generation !== lastRequest.current) return;
        setSession(data);
        if (data.active) timer = setTimeout(()=>void poll(), 250);
        else {void loadHistory().catch(()=>{});}
      } catch (error) {
        if (!cancelled) {setMessage((error as Error).message); timer=setTimeout(()=>void poll(),2000);}
      }
    }
    void poll();
    return ()=>{cancelled=true;clearTimeout(timer);};
  },[id]);
  async function start() {
    setBusy(true); setMessage('');
    try {
      let uploadId = '';
      if (needsFile.has(kind)) {
        if (!file) throw new Error('请先选择输入文件');
        const body = new FormData(); body.append('file',file);
        const uploaded = await uploadWithProgress<{id: string}>('/live/uploads',body);
        uploadId = uploaded.id;
      }
      const board = ports.ports.find(p=>p.port===zynq), source = ports.ports.find(p=>p.port===capture);
      const data = await post<{id: string}>('/live/sessions', {kind, upload_id:uploadId, seconds, sample_limit:limit, realtime,
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
  const active = Boolean(session?.active);
  const result = session?.result, rate = result?.header?.fs ?? null;
  const resultDivisor = rate ?? 1;
  const scale = result?.header?.scale;
  const secondary: PlotPoint[] = [];
  let previousFiltered: number | null = null;
  if (resultTrace==='both') for (const sample of result?.samples ?? []) {
    if (sample.filt===null) continue;
    secondary.push({t:sample.index/resultDivisor,v:scale?sample.filt/scale:sample.filt,
      breakBefore:previousFiltered!==null && sample.index!==previousFiltered+1});
    previousFiltered=sample.index;
  }
  const waveform: PlotPoint[] = [];
  let previousResult: number | null = null;
  for (const sample of result?.samples ?? []) {
    const value = resultTrace==='filt' ? sample.filt : sample.raw;
    if (value === null) continue;
    waveform.push({t:sample.index/resultDivisor, v:scale ? value/scale : value,
      breakBefore:previousResult!==null && sample.index!==previousResult+1});
    previousResult=sample.index;
  }
  const sourcePlot = sourceTrace(session?.source_samples ?? [], session?.kind ?? '', channel, sourceMode);
  const sourcePoints = sourcePlot.points, sourceRate = sourcePlot.fs;
  const span = (points: PlotPoint[], fs: number) => Math.max(1/fs,(points[points.length-1]?.t ?? 0)-(points[0]?.t ?? 0));
  const markers = (result?.events ?? []).filter(e=>e.index!==null).map(e=>({t:e.index!/resultDivisor,label:String(e.seq)}));
  const shownState = session ? states[String(session.info.state)] ?? String(session.info.state) : '未开始';
  const samples = session?.info.source_samples ?? session?.capture_info.total ?? session?.capture_info.samples;
  return <>
    <section><div className="detail-head"><div><p className="eyebrow">采集 · 中转 · 保存</p><h1>实时与板卡</h1></div><span className={`badge ${session?.info.error?'badge-bad':active?'badge-ok':'badge-muted'}`}>{shownState}</span></div>
      <p>电脑接收采集数据，Zynq处理后返回结果。演示与日志可离线运行；本页不运行QRS或分类模型。</p>
      <div className="live-controls">
        <label>数据来源<select value={kind} disabled={active || busy} onChange={e=>{setKind(e.target.value);setFile(null);}}>{modes.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
        {needsFile.has(kind) && <label>输入文件（≤32MiB）<input key={kind} type="file" accept={kind==='log'?'.log':'.csv'} disabled={active || busy} onChange={e=>setFile(e.target.files?.[0] ?? null)}/></label>}
        {needsBoard.has(kind) && <label>Zynq USB_UART<select value={zynq} disabled={active || busy} onChange={e=>{setZynq(e.target.value);if(e.target.value===capture)setCapture('');}}><option value="">请选择</option>{ports.ports.map(p=><option key={p.port} value={p.port}>{p.port} · {p.label}</option>)}</select></label>}
        {needsCapture.has(kind) && <label>采集USB接收器<select value={capture} disabled={active || busy} onChange={e=>setCapture(e.target.value)}><option value="">请选择</option>{ports.ports.filter(p=>p.port!==zynq || !needsBoard.has(kind)).map(p=><option key={p.port} value={p.port}>{p.port} · {p.label}</option>)}</select></label>}
        {kind==='demo' && <label>演示秒数<input type="number" min="1" max="300" value={seconds} disabled={active || busy} onChange={e=>setSeconds(Number(e.target.value))}/></label>}
        {needsCapture.has(kind) && <label>采集点数上限<input type="number" min="1" max="1800000" value={limit} disabled={active || busy} onChange={e=>setLimit(Number(e.target.value))}/></label>}
      </div>
      <div className="actions"><button disabled={active || busy} onClick={()=>void start()}>开始并记录</button><button className="secondary" disabled={!active || busy} onClick={()=>void stop()}>停止并保存</button>
        <button className="secondary" disabled={active || busy} onClick={()=>void refresh().catch(error=>setMessage(error.message))}>刷新端口</button>
        <label className="inline"><input type="checkbox" checked={realtime} disabled={active || busy} onChange={e=>setRealtime(e.target.checked)}/>按采样节拍回放</label></div>
      <p className="hint">标准CSV须为 index,sample,fs,scale，360/500Hz与4096单位每mV；厂商CSV/34字节数据走独立换算合同。请选择匹配的板端应用。停止后保留历史画面。</p>
      {ports.warnings.map((warning,index)=><p className="hint" key={index}>{warning}</p>)}
      <p role="status" className={message || session?.info.error || session?.persistence_error?'notice notice-error':'hint'}>{message || String(session?.info.error || session?.persistence_error || session?.scope || '就绪；每次运行建立新目录，不覆盖旧记录。')}</p>
      <div className="stat-grid"><div><span>心率（次/分）</span><strong>{number(result?.hr,1)}</strong></div><div><span>RR（ms）</span><strong>{number(result?.rr_ms,1)}</strong></div><div><span>心拍类别</span><strong>{result?.cls ?? '未提供'}</strong></div><div><span>累计来源点数</span><strong>{number(samples)}</strong></div></div>
      {(session?.kind==='demo' || result?.header?.source==='SYNTH') && <p className="notice">合成波形，事件是预设标记。它们不代表算法检测或分类结果。</p>}
    </section>
    {session && <section><div className="record-toolbar"><h2>波形与事件{!active?' · 历史数据':''}</h2><button className="secondary" onClick={()=>save(`/live/sessions/${id}/svg`,'ecg.svg')}>导出结果SVG</button></div>
      {session.info.state==='waiting' && <p className="notice">暂无新串口字节，数值为上次接收值；这不等于物理断连。</p>}
      {session.source_samples.length>0 && <><div className="wave-toolbar"><strong>来源</strong>{!session.kind.startsWith('standard') && <select value={channel} onChange={e=>{setChannel(e.target.value);if(e.target.value!=='ecg' && sourceMode==='mv')setSourceMode('code');}}><option value="ecg">CH2 · ECG</option><option value="resp">CH1 · 呼吸</option></select>}
        {!session.kind.startsWith('standard') && <select aria-label="来源幅值" value={sourceMode} onChange={e=>setSourceMode(e.target.value as SourceTrace)}><option value="code">ADC原码</option>{channel==='ecg' && <option value="mv">标称电压 · mV</option>}<option value="vendor">厂商滤波列（如有）</option></select>}</div>
        <Waveform points={sourcePoints} offset={sourcePoints[0]?.t ?? 0} duration={span(sourcePoints,sourceRate)} unit={sourcePlot.unit}/>
        {sourceMode==='mv' && !session.kind.startsWith('standard') && <p className="hint">电压由未额外数字滤波的CH2原码换算，保留直流；Zynq输入另有去直流和int16量化，两者幅值不必相同。历史记录若无电压字段则不绘制。</p>}</>}
      <div className="wave-toolbar"><strong>{needsBoard.has(session.kind)?'Zynq返回':'日志/演示'}</strong><select value={resultTrace} onChange={e=>setResultTrace(e.target.value)}><option value="raw">raw</option><option value="filt">filt（未提供不绘制）</option><option value="both">raw绿色 / filt蓝色</option></select><span>{result?.header?.detector ?? '尚无合法会话头'}</span></div>
      <Waveform points={waveform} secondary={secondary} offset={waveform[0]?.t ?? 0} duration={span(waveform,resultDivisor)} axisUnit={rate?'s':'样本号'} unit={scale?'mV（声明比例）':'码值（未标定）'} markers={markers}/>
      <div className="live-table"><table><thead><tr>{['事件号','源位置（样本号）','RR（点）','心率','类别'].map(title=><th key={title}>{title}</th>)}</tr></thead><tbody>{[...(result?.events ?? [])].reverse().map(event=><tr key={event.seq}><td>{event.seq}</td><td>{event.pos}{event.index===null?'（不在当前可见窗口）':''}</td><td>{event.rr ?? '未知'}</td><td>{number(event.hr,1)}</td><td>{result?.header && (result.header.caps & 16) ? event.cls==='?'?'未知':event.cls : '未提供'}</td></tr>)}</tbody></table></div>
      <details><summary>诊断与保存文件</summary><pre className="mono-wrap">{JSON.stringify({session:id,info:session.info,capture:session.capture_info,diagnostics:session.diagnostics},null,2)}</pre>
        <div className="actions">{session.files.map(name=><button key={name} className="secondary" disabled={active} onClick={()=>save(`/live/sessions/${id}/files/${name}`,name.substring(name.lastIndexOf('/')+1))}>{name}</button>)}</div>
      </details><p className="hint">页面离开、刷新或网络中断不会停止服务端记录；回到本页选择会话后可继续查看、停止。显示缓存最多4096点、256个事件；完整记录在下载文件中。</p>
    </section>}
    <section><h2>实时会话记录</h2><button className="secondary" onClick={()=>void loadHistory().catch(error=>setMessage(error.message))}>刷新列表</button>
      {history.map(row=><div className="row" key={row.id}><span>{new Date(row.created*1000).toLocaleString()} · {modes.find(([key])=>key===row.kind)?.[1] ?? row.kind} · {row.active?'进行中':'历史'}</span><button className="secondary" onClick={()=>{if(row.id!==id)setSession(null);setKind(row.kind);setFile(null);setId(row.id);}}>查看</button></div>)}
    </section>
  </>;
}
