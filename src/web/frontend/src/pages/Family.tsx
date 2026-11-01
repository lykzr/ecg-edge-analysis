// 账户模块：家庭业务页面与接口。
import { useEffect, useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { request, post, Grant, Notification } from '../services/api';
export default function Family(){
  const [rows,setRows]=useState<Grant[]>([]),[notes,setNotes]=useState<Notification[]>([]),[username,setUsername]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[refreshing,setRefreshing]=useState(false);
  async function refresh(){setRefreshing(true);try{const [g,n]=await Promise.all([request<Grant[]>('/family/grants'),request<Notification[]>('/family/notifications')]);setRows(g);setNotes(n);}finally{setRefreshing(false);}}
  useEffect(()=>{void refresh().catch(e=>setMessage(e.message));},[]);
  async function change(id?:string){if(busy)return;setBusy(true);setMessage('');try{if(id)await request('/family/grants/'+id,{method:'DELETE'});else await post('/family/grants',{username:username.trim()});if(!id)setUsername('');await refresh();setMessage(id?'授权已撤回':'已开放记录查看权限');}catch(e){setMessage((e as Error).message);}finally{setBusy(false);}}
  return <section><p className="eyebrow">用户与家庭协同</p><h1>家庭协同</h1><p>向已注册账号开放记录查看权限。对方可查看测量与分析，不能修改；撤回后停止共享。</p><button className="secondary" disabled={busy||refreshing} onClick={()=>void refresh().catch(e=>setMessage(e.message))}>{refreshing?'加载中…':'刷新授权与通知'}</button><form onSubmit={(e:FormEvent)=>{e.preventDefault();void change();}}><label>家属用户名<input required disabled={busy} value={username} onChange={e=>setUsername(e.target.value)} /></label><button disabled={busy||!username.trim()}>授权查看</button></form><p role="status">{message}</p><h2>我发出的授权</h2>{!refreshing&&!rows.length&&<p>暂无授权</p>}{rows.map(g=><div className="row" key={g.id}><span>{g.username} · {g.active?'有效':'已撤回'}</span>{Boolean(g.active)&&<button className="secondary" disabled={busy} onClick={()=>void change(g.id)}>撤回</button>}</div>)}<h2>站内通知</h2><p><Link className="button secondary" to="/records?shared=true&range=all">查看授权给我的记录</Link></p>{!refreshing&&!notes.length&&<p>暂无通知</p>}{notes.map(n=><p key={n.id}>{n.owner_username ? `${n.owner_username} 已向你开放记录查看权限` : n.message} · 站内可查看，非外部投递</p>)}</section>;
}
