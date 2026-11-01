import type { PlotPoint } from './waveformGeometry';

export interface SourceSample {
  index: number; time_s: number; resp_raw: number; ecg_raw: number;
  resp_filtered: number | null; ecg_filtered: number | null;
  ecg_nominal_mv?: number;
}
export type SourceTrace = 'code' | 'mv' | 'vendor';

/** 只选择后台已声明的数据；缺失电压不补算，厂商滤波值不冒充mV。 */
export function sourceTrace(samples: SourceSample[], kind: string, channel: string, trace: SourceTrace) {
  const standard = kind.startsWith('standard');
  const fs = kind === 'standard360' ? 360 : 500;
  const unit = standard ? 'int16 / 4096单位每mV' : trace === 'mv'
    ? 'CH2标称mV（2.42V / 增益6，未标定）' : trace === 'vendor'
      ? '厂商滤波值（单位未确认）' : '有符号24位ADC码（未标定）';
  const points: PlotPoint[] = [];
  let previous: number | null = null;
  for (const sample of samples) {
    const value = standard ? sample.ecg_raw - 8388608 : trace === 'mv'
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
