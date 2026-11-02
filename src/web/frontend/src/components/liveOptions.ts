import type {SourceSample, SourceTrace} from './liveSource';

export type LiveCategory = 'capture' | 'file' | 'demo' | 'advanced';

/** 统一CSV入口仅识别路由；完整内容仍由后端按各自合同校验。 */
export function identifyCsv(prefix: string): 'bridge_csv' | 'standard360' | 'standard500' {
  const [header, first] = prefix.replace(/^\uFEFF/, '').split(/\r?\n/);
  if (header === 'timestamp(s),resp_raw,ecg_raw,resp_filtered,ecg_filtered') return 'bridge_csv';
  if (header === 'index,sample,fs,scale') {
    const row = first?.split(',');
    if (row?.length === 4 && row[3] === '4096') {
      if (row[2] === '500') return 'standard500';
      if (row[2] === '360') return 'standard360';
    }
    throw new Error('CSV 须声明 360 或 500 Hz，比例为 4096，且包含数据。');
  }
  throw new Error('无法识别波形CSV；请选择含 ecg_raw 的五列数据，或 index,sample,fs,scale 格式。');
}

export function categoryFor(kind: string): LiveCategory {
  if (['bridge_serial', 'vendor_serial'].includes(kind)) return 'capture';
  if (['bridge_csv', 'vendor_csv', 'standard360', 'standard500'].includes(kind)) return 'file';
  return kind === 'demo' ? 'demo' : 'advanced';
}

export type SourceSignal = 'original' | 'vendor' | 'baseline' | 'display' | 'resp';
/** 切换通道时选该通道的默认显示；缺列仍由selectSourceTrace回退。 */
export function defaultSourceTrace(channel: string): SourceTrace {
  return channel==='resp'?'resp':'mv';
}
const finite = (value: unknown) => typeof value === 'number' && Number.isFinite(value);

/** 保持信号、单位两个控件；旧记录没有的新列不显示，也不补算。 */
export function sourceSignals(samples: SourceSample[], channel: string): SourceSignal[] {
  const options: SourceSignal[] = ['original'];
  if (samples.some(s=>finite(channel==='ecg'?s.ecg_filtered:s.resp_filtered))) options.push('vendor');
  if (channel==='resp') {
    if (samples.some(s=>finite(s.resp_display_code))) options.push('resp');
  } else {
    if (samples.some(s=>finite(s.ecg_baseline_code) || finite(s.ecg_baseline_mv))) options.push('baseline');
    if (samples.some(s=>finite(s.ecg_display_code) || finite(s.ecg_display_mv))) options.push('display');
  }
  return options;
}

export function sourceSignal(trace: SourceTrace): SourceSignal {
  return trace.startsWith('baseline_')?'baseline':trace.startsWith('display_')?'display':trace==='mv'||trace==='code'?'original':trace as SourceSignal;
}

export function selectSourceTrace(samples: SourceSample[], channel: string, signal: SourceSignal, mv: boolean): SourceTrace {
  if (!sourceSignals(samples,channel).includes(signal)) signal='original';
  if (signal==='vendor' || signal==='resp') return signal;
  const prefix = signal==='original'?'':signal+'_';
  const voltage: SourceTrace = signal==='original'?'mv':(prefix+'mv') as SourceTrace;
  const code: SourceTrace = signal==='original'?'code':(prefix+'code') as SourceTrace;
  const hasVoltage = samples.some(s=>finite(voltage==='mv'?s.ecg_nominal_mv:s[voltage==='baseline_mv'?'ecg_baseline_mv':'ecg_display_mv']));
  const hasCode = signal==='original' || samples.some(s=>finite(s[code==='baseline_code'?'ecg_baseline_code':'ecg_display_code']));
  return channel==='ecg' && hasVoltage && (mv || !hasCode)?voltage:code;
}

export function hasFilteredResult(caps: number, samples: {filt: number | null}[]): boolean {
  return Boolean(caps & 2) && samples.some(sample => typeof sample.filt === 'number' && Number.isFinite(sample.filt));
}

export function sourceAvailability(samples: {ecg_nominal_mv?: number; ecg_filtered: number | null; resp_filtered: number | null}[], channel: string) {
  return {
    voltage: channel === 'ecg' && samples.some(sample => typeof sample.ecg_nominal_mv === 'number' && Number.isFinite(sample.ecg_nominal_mv)),
    vendor: samples.some(sample => {const value = channel === 'ecg' ? sample.ecg_filtered : sample.resp_filtered; return typeof value === 'number' && Number.isFinite(value);}),
  };
}
