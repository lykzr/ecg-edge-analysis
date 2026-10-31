/** 保留原始时刻，缺口断线；抽稀只影响绘图，不影响计数、保存或事件位置。 */
export interface PlotPoint {t: number; v: number; breakBefore?: boolean;}

export function envelope(points: PlotPoint[], buckets = 600): PlotPoint[] {
  if (buckets < 1) throw new Error('绘图桶数须为正');
  if (points.length <= buckets * 2) return points;
  const size = Math.ceil(points.length / buckets);
  const output: PlotPoint[] = [];
  for (let start = 0; start < points.length; start += size) {
    const end = Math.min(points.length, start + size);
    let low = start, high = start;
    const required = new Set<number>([start, end - 1]);
    for (let index = start; index < end; index++) {
      if (points[index].v < points[low].v) low = index;
      if (points[index].v > points[high].v) high = index;
      if (points[index].breakBefore) {required.add(index); if (index > 0) required.add(index - 1);}
    }
    required.add(low); required.add(high);
    for (const index of [...required].sort((a, b) => a - b)) {
      if (output[output.length - 1] !== points[index]) output.push(points[index]);
    }
  }
  return output;
}

export function valuePoints(values: number[], offset: number, duration: number, samplingHz?: number): PlotPoint[] {
  const step = samplingHz && samplingHz > 0 ? 1 / samplingHz : duration / Math.max(values.length, 1);
  return values.map((v, index) => ({t: offset + index * step, v}));
}

export function segments(points: PlotPoint[]): PlotPoint[][] {
  const lines: PlotPoint[][] = [];
  for (const point of points) {
    if (!Number.isFinite(point.t) || !Number.isFinite(point.v)) continue;
    if (!lines.length || point.breakBefore) lines.push([]);
    lines[lines.length - 1].push(point);
  }
  return lines;
}
