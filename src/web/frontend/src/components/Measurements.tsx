import {useEffect, useRef, useState} from 'react';
import {Link, useLocation, useNavigate} from 'react-router-dom';
import {AnalysisTask, post, request} from '../services/api';
interface Measurement {id:string; kind:string; created:number; active:boolean; info:Record<string,unknown>; analysis_count:number; owner_username:string; owned:boolean;}
interface Version {id:string; status:string; record_id:string|null;}
const names:Record<string,string> = {demo:'合成演示',log:'日志回放',result_serial:'板卡结果',vendor_csv:'CSV回放',vendor_serial:'蓝牙采集',bridge_csv:'CSV与板卡',bridge_serial:'蓝牙与板卡',standard360:'CSV与板卡 · 360Hz',standard500:'CSV与板卡 · 500Hz'};
export default function Measurements({days=0,shared=false}:{days?:number;shared?:boolean}) {
  const [rows,setRows]=useState<Measurement[]>([]), [error,setError]=useState(''), [busy,setBusy]=useState('');
  const [versions,setVersions]=useState<Record<string,Version[]>>({});
  const generation=useRef(0);
  const [loading,setLoading]=useState(true);
  const navigate=useNavigate();
  const location=useLocation();
  const returnState={returnTo:location.pathname+location.search};
  async function refresh(){const current=++generation.current;setLoading(true);try{const next=await request<Measurement[]>('/live/sessions?shared='+shared);if(current!==generation.current)return;setRows(next);setError('');}catch(e){if(current===generation.current)setError((e as Error).message);}finally{if(current===generation.current)setLoading(false);}}
  useEffect(()=>{setRows([]);setVersions({});void refresh();return()=>{generation.current++;};},[shared]);
  async function analyze(id:string){setBusy(id);setError('');try{const task=await post<AnalysisTask>('/live/sessions/'+id+'/analyze');navigate('/analyze?task='+task.id,{state:returnState});}catch(e){setError((e as Error).message);}finally{setBusy('');}}
  async function showVersions(id:string){if(versions[id]){setVersions(old=>{const next={...old};delete next[id];return next;});return;}const current=generation.current;try{const result=await request<Version[]>('/live/sessions/'+id+'/analyses');if(current===generation.current)setVersions(old=>({...old,[id]:result}));}catch(e){if(current===generation.current)setError((e as Error).message);}}
  const start=new Date();start.setDate(start.getDate()-days+1);start.setHours(0,0,0,0);
  const visible=rows.filter(row=>!days || row.created*1000>=start.getTime()).sort((a,b)=>a.owner_username.localeCompare(b.owner_username)||b.created-a.created);
  return <section><div className="record-toolbar"><h2>{shared?'共享给我的测量':'我的测量记录'}</h2><button className="secondary" disabled={loading} onClick={()=>void refresh()}>{loading?'加载中…':'刷新测量'}</button></div>
    <p className="hint">本页显示 {visible.length} 次会话，其中已停止且未报错 {visible.filter(row=>!row.active && row.info.state==='stopped' && !row.info.error && row.kind!=='demo' && row.kind!=='log').length} 次；这不代表信号质量或分类通过。一次测量可有多个分析版本。</p>
    {error&&<p role="alert" className="notice notice-error">{error}</p>}
    {!loading&&!error&&!visible.length&&<p>此时间范围内暂无测量记录。</p>}
    {visible.map(row=><article className="measurement-item" key={row.id}><div className="measurement-row"><div className="record-main"><span className="owner-tag">用户：{row.owner_username}{!row.owned?' · 共享只读':''}</span><strong>{new Date(row.created*1000).toLocaleString()}</strong><small>{names[row.kind]??row.kind}</small></div>
      <span className={'badge '+(row.active?'badge-info':row.info.state==='error'?'badge-bad':'badge-muted')}>{row.active?'进行中':row.info.state==='error'?'出错中断':'已停止保存'}</span>
      <div className="measurement-actions"><Link className="button secondary" state={returnState} to={'/live?session='+row.id}>查看</Link>
      {row.owned && <button disabled={row.active||Boolean(busy)} onClick={()=>void analyze(row.id)}>{busy===row.id?'打开中…':row.analysis_count?'查看分析':'分析'}</button>}
      <button className="secondary" onClick={()=>void showVersions(row.id)} aria-expanded={Boolean(versions[row.id])}>{versions[row.id]?'收起版本':'分析版本（'+(row.analysis_count ?? 0)+'）'}</button></div></div>
      {Boolean(row.info.error)&&<details className="measurement-error"><summary>{String(row.info.error).includes('Timeout')?'连接超时 · 查看详情':'运行异常 · 查看详情'}</summary><p className="mono-wrap">{String(row.info.error)}</p></details>}
      {versions[row.id]&&<div className="measurement-versions">{!versions[row.id].length?'尚无分析版本':versions[row.id].map(v=><p key={v.id}>{v.record_id?<Link className="link" state={returnState} to={'/records/'+v.record_id}>查看分析结果</Link>:<Link className="link" state={returnState} to={'/analyze?task='+v.id}>查看分析任务</Link>} · {{pending:'等待中',running:'分析中',completed:'已完成',failed:'失败',cancelled:'已取消'}[v.status]??v.status}</p>)}</div>}
    </article>)}
  </section>;
}
