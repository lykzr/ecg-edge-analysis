import type { PlotPoint } from './waveformGeometry';

export interface SourceSample {
  index: number; time_s: number; resp_raw: number; ecg_raw: number;
  resp_filtered: number | null; ecg_filtered: number | null;
  ecg_nominal_mv?: number;
  resp_display_code?: number | null;
  ecg_baseline_code?: number | null; ecg_baseline_mv?: number | null;
  ecg_display_code?: number | null; ecg_display_mv?: number | null;
}
export type SourceTrace = 'code' | 'mv' | 'vendor' | 'resp' | 'baseline_code' | 'baseline_mv' | 'display_code' | 'display_mv';

/** 只选择后台已声明的数据；缺失电压不补算，厂商滤波值不冒充mV。 */
export function sourceTrace(samples: SourceSample[], kind: string, channel: string, trace: SourceTrace) {
  const standard = kind.startsWith('standard');
  const fs = kind === 'standard360' ? 360 : 500;
  const processed = trace.startsWith('baseline_') || trace.startsWith('display_');
  const unit = standard ? 'int16 / 4096单位每mV' : processed
    ? (trace.endsWith('_mv') ? 'mV' : 'ADC码') : trace === 'mv'
    ? 'mV' : trace === 'vendor'
      ? '设备滤波值（单位未确认）' : '有符号24位ADC码（未标定）';
  const points: PlotPoint[] = [];
  if (channel === 'resp' && trace === 'resp') {
    let previous: number | null = null;
    for (const sample of samples) {
      if (typeof sample.resp_display_code !== 'number' || !Number.isFinite(sample.resp_display_code)) continue;
      points.push({t:sample.index/fs,v:sample.resp_display_code,
        breakBefore:previous !== null && sample.index !== previous + 1});
      previous = sample.index;
    }
    return {points, fs, unit: 'PC呼吸滤波 · ADC码（未标定）'};
  }
  let previous: number | null = null;
  for (const sample of samples) {
    const value = standard ? sample.ecg_raw - 8388608 : processed
      ? (channel !== 'ecg' ? null : trace === 'baseline_code' ? sample.ecg_baseline_code
        : trace === 'baseline_mv' ? sample.ecg_baseline_mv
        : trace === 'display_code' ? sample.ecg_display_code : sample.ecg_display_mv) : trace === 'mv'
      ? (channel === 'ecg' ? sample.ecg_nominal_mv : null) : trace === 'vendor'
        ? (channel === 'ecg' ? sample.ecg_filtered : sample.resp_filtered)
        : (channel === 'ecg' ? sample.ecg_raw : sample.resp_raw) - 8388608;
    if (typeof value !== 'number' || !Number.isFinite(value)) continue;
    points.push({t: sample.index / fs, v: value,
      breakBefore: previous !== null && sample.index !== previous + 1});
    previous = sample.index;
  }
  return { points, fs, unit };
}
