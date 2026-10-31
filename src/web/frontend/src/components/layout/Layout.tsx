import { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { post } from '../../services/api';
export default function Layout({children}: {children:ReactNode}) {
  async function logout() {
    try {await post('/auth/logout');} finally {sessionStorage.removeItem('ecg_token');window.dispatchEvent(new Event('ecg:logout'));}
  }
  return <><header className="app-header"><strong>未卜心知</strong><span>ECG边缘分析与记录</span><button className="secondary" onClick={()=>{void logout().catch(()=>{});}}>退出</button></header>
    <main><aside>实时页接收采集数据并与Zynq中转，心拍结果来自板端；导入分析页为独立离线流程。未接入分类模型时显示“未提供”，演示标记不代表检测结果。本系统为研究原型。</aside>
    <nav><NavLink to="/">概览</NavLink><NavLink to="/live">实时与板卡</NavLink><NavLink to="/analyze">导入与分析</NavLink><NavLink to="/records">历史记录</NavLink><NavLink to="/family">家庭协同</NavLink></nav>{children}</main></>;
}
