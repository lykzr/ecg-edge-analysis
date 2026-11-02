import { useId } from 'react';
import { envelope, valuePoints, segments, PlotPoint, displayWaveforms } from './waveformGeometry';

export default function Waveform({values = [], points, duration, unit, offset = 0, samplingHz, markers = [], axisUnit = 's', secondary = []}: {
  values?: number[]; points?: PlotPoint[]; duration: number; unit: string; offset?: number;
  samplingHz?: number; markers?: {t: number; label: string}[]; axisUnit?: 's' | '样本号'; secondary?: PlotPoint[];
}) {
  const gridId = useId();
  const fromWindow = Boolean(points && points.length);
  const source = envelope(fromWindow ? points! : valuePoints(values, offset, duration, samplingHz));
  const second = envelope(secondary);
  if (!source.length && !second.length) return <p className="empty-state">尚无波形数据。请选择来源后开始；缺失数据不会补零。</p>;
  const display=displayWaveforms(source,second);
  const {min,max}=display;
  const span = max - min || 1;
  const left = 76, right = 964, top = 26, bottom = 198;
  const xOf = (t: number) => left + Math.min(1, Math.max(0, (t-offset)/Math.max(duration,1e-9)))*(right-left);
  const coordinate = (p: PlotPoint) => `${xOf(p.t).toFixed(2)},${(bottom-(p.v-min)/span*(bottom-top)).toFixed(2)}`;
  return <figure><svg viewBox="0 0 1000 240" role="img" aria-label={`信号波形，${offset.toFixed(2)}到${(offset+duration).toFixed(2)}${axisUnit}`}>
    <defs><pattern id={gridId} width="50" height="40" patternUnits="userSpaceOnUse">
      <path d="M 50 0 L 0 0 0 40" fill="none" stroke="#dce8e3"/></pattern></defs>
    <rect width="1000" height="240" fill={`url(#${gridId})`}/>
    {segments(display.primary).map((line, index)=><polyline key={index} points={line.map(coordinate).join(' ')} fill="none" stroke="#157a70" strokeWidth="1.3"/>)}
    {segments(display.secondary).map((line, index)=><polyline key={index} points={line.map(coordinate).join(' ')} fill="none" stroke="#3179b7" strokeWidth="1.3"/>)}
    {markers.filter(m=>m.t>=offset && m.t<=offset+duration).map((m,index)=><g key={index}>
      <line x1={xOf(m.t)} x2={xOf(m.t)} y1={top} y2={bottom} stroke="#b16a1e" strokeDasharray="4 4"/>
      <text x={xOf(m.t)+3} y={top+12} className="wave-label">{m.label}</text></g>)}
    <text x={left-6} y={top+4} textAnchor="end" className="wave-label">{max.toFixed(3)}</text>
    <text x={left-6} y={bottom} textAnchor="end" className="wave-label">{min.toFixed(3)}</text>
    <text x={left} y="224" className="wave-label">{offset.toFixed(2)} {axisUnit}</text>
    <text x={right} y="224" textAnchor="end" className="wave-label">{(offset+duration).toFixed(2)} {axisUnit}</text>
  </svg><figcaption>{unit}</figcaption></figure>;
}
