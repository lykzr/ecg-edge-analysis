import { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { post } from '../../services/api';
export default function Layout({children}: {children:ReactNode}) {
  async function logout() {
    try {await post('/auth/logout');} finally {sessionStorage.removeItem('ecg_token');window.dispatchEvent(new Event('ecg:logout'));}
  }
  return <><header className="app-header"><strong>未卜心知</strong><span>Zynq-7020 心电边缘分析</span><button className="secondary" onClick={()=>{void logout().catch(()=>{});}}>退出</button></header>
    <main>
    <nav><NavLink to="/live">检测与加速</NavLink><NavLink to="/analyze">导入与分析</NavLink><NavLink to="/records">历史记录</NavLink></nav>{children}</main></>;
}
