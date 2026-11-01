import {Link, useLocation} from 'react-router-dom';

export function returnPath(state: unknown, fallback='/records'): string {
  const value=(state as {returnTo?:unknown}|null)?.returnTo;
  return typeof value==='string' && ['/records','/analyze','/live'].some(path=>value===path || value.startsWith(path+'/') || value.startsWith(path+'?')) ? value : fallback;
}

export default function BackLink({fallback='/records', label='返回上一页'}:{fallback?:string;label?:string}) {
  const location=useLocation();
  return <Link className="button secondary" to={returnPath(location.state,fallback)}>{label}</Link>;
}
