import { RecordTrendPoint } from '../services/api';
import {trendSegments, trendTicks} from './trendGeometry';

export default function TrendChart({days}: {days: RecordTrendPoint[]}) {
  const total = days.reduce((sum, point) => sum + point.records, 0);
  if (!total) return <p className="empty-state">此时间范围内暂无分析结果。完成分析后显示每日分析版本数与平均心率。</p>;

  const width = 760;
  const height = 200;
  const padding = {top: 16, right: 18, bottom: 30, left: 38};
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const maxRecords = Math.max(1, ...days.map(point => point.records));
  const rates = days.map(point => point.heart_rate_bpm).filter((value): value is number => value != null);
  const maxRate = Math.max(100, ...rates);
  const minRate = Math.min(40, ...rates);
  const slot = plotWidth / days.length;
  const barWidth = Math.max(2, Math.min(18, slot * 0.55));
  const x = (index: number) => padding.left + slot * index + slot / 2;
  const yRecords = (value: number) => padding.top + plotHeight - (value / maxRecords) * plotHeight;
  const yRate = (value: number) => padding.top + plotHeight - ((value - minRate) / (maxRate - minRate || 1)) * plotHeight;

  const lines = trendSegments(days.map(point=>point.heart_rate_bpm));
  const ticks = trendTicks(days.length);

  return <figure className="trend-chart">
    <svg viewBox={`0 0 ${width} ${height}`} role="img"
         aria-label={`近 ${days.length} 天趋势：共 ${total} 个分析版本，心率折线`}>
      <pattern id="trend-grid" width="38" height="38" patternUnits="userSpaceOnUse">
        <path d="M 38 0 L 0 0 0 38" fill="none" stroke="#e3ece9" />
      </pattern>
      <rect x={padding.left} y={padding.top} width={plotWidth} height={plotHeight} fill="url(#trend-grid)" />
      {days.map((point, index) => {
        const barHeight = (point.records / maxRecords) * plotHeight;
        const hint = point.heart_rate_bpm == null
          ? `${point.date}：${point.records} 条，暂无心率`
          : `${point.date}：${point.records} 条，平均心率 ${point.heart_rate_bpm}`;
        return <g key={point.date}>
          <title>{hint}</title>
          <rect className="trend-bar" x={x(index) - barWidth / 2} y={yRecords(point.records)}
                width={barWidth} height={Math.max(point.records ? 2 : 0, barHeight)} rx="2" />
          {ticks.includes(index) && <text x={x(index)} y={height - 10} textAnchor="middle"
                className="trend-label">{point.date.slice(5)}</text>}
        </g>;
      })}
      {lines.map((indices,i)=><polyline key={i} className="trend-line" points={indices.map(index=>[x(index),yRate(days[index].heart_rate_bpm!)].join(',')).join(' ')} fill="none" />)}
      {days.map((point, index) => point.heart_rate_bpm == null ? null :
        <circle key={`dot-${point.date}`} className="trend-dot" cx={x(index)} cy={yRate(point.heart_rate_bpm)} r="2.5" />)}
      <text x={padding.left - 6} y={padding.top + 4} textAnchor="end" className="trend-label">{maxRecords}</text>
      <text x={padding.left - 6} y={padding.top + plotHeight} textAnchor="end" className="trend-label">0</text>
    </svg>
    <figcaption>柱：每日分析版本数（最高 {maxRecords} 条）· 线：已有心率的日均值 · 时区由浏览器提供</figcaption>
  </figure>;
}
