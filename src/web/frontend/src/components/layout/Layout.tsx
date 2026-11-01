import { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { post } from '../../services/api';
export default function Layout({children}: {children:ReactNode}) {
  async function logout() {
    try {await post('/auth/logout');} finally {sessionStorage.removeItem('ecg_token');window.dispatchEvent(new Event('ecg:logout'));}
  }
  return <><header className="app-header"><strong>未卜心知</strong><span>ECG边缘分析与记录</span><button className="secondary" onClick={()=>{void logout().catch(()=>{});}}>退出</button></header>
    <main><aside>三个页面共用当前账号的测量记录：实时测量后可在历史查看，也可继续分析。心拍检测结果来自板端，未接入分类模型时不输出分类。本系统为研究原型。</aside>
    <nav><NavLink to="/live">实时与板卡</NavLink><NavLink to="/analyze">导入与分析</NavLink><NavLink to="/records">历史记录</NavLink><NavLink to="/family">家庭协同</NavLink></nav>{children}</main></>;
}
