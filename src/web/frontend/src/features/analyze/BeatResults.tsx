import { useState } from 'react';
import { Prediction } from '../../services/api';

export default function BeatResults({prediction}: {prediction: Prediction}) {
  const [page, setPage] = useState(0);
  const beats = prediction.beats;
  const items = beats?.items ?? [];
  const pages = Math.max(1, Math.ceil(items.length / 50));
  const current = Math.min(page, pages - 1);
  return <section>
    <h2>电脑端逐心拍分类</h2>
    <p>模型 {prediction.model_version} · 500 Hz · {prediction.preprocess} · N/S/VF</p>
    <p className="notice">研究联调结果，尚未通过当前分类验收（各类比例90%，F子类召回75%）；这不是单拍正确率。N类不能作为健康结论；VF为V/E/F合并，不表示心室颤动。板端原类别保持原样。</p>
    <p>N {beats?.by_type?.N ?? 0} 拍 · S {beats?.by_type?.S ?? 0} 拍 · VF {beats?.by_type?.VF ?? 0} 拍 · 未分类 {beats?.unclassified_count ?? 0} 拍</p>
    <div className="live-table"><table><thead><tr>{['模型拍号', 'R位置（秒/样本）', '类别', '模型概率', '板端事件号', '位置差（样本）'].map(t=><th key={t}>{t}</th>)}</tr></thead>
      <tbody>{items.slice(current * 50, (current + 1) * 50).map(b=><tr key={b.beat_id}>
        <td>{b.beat_id}</td><td>{b.r_seconds.toFixed(3)} / {b.r_sample500}</td>
        <td>{b.valid ? b.label : `未分类（输入状态${b.input_status}）`}</td>
        <td>{b.probabilities ? `${(Math.max(...b.probabilities)*100).toFixed(1)}%` : '—'}</td>
        <td>{b.board_event_id ?? (b.board_association === 'ambiguous' ? '关联不唯一' : '未关联')}</td>
        <td>{b.board_delta_samples ?? '—'}</td>
      </tr>)}</tbody></table></div>
    <div className="actions"><button className="secondary" disabled={current===0} onClick={()=>setPage(current-1)}>上一页</button>
      <span>第{current+1}/{pages}页 · 每页50拍</span>
      <button className="secondary" disabled={current+1>=pages} onClick={()=>setPage(current+1)}>下一页</button></div>
    <p className="hint">概率是未校准的模型输出，不等于诊断可靠性。全部逐拍数据保留在记录JSON导出中；首拍RR未知或窗口不足时保留未分类。</p>
  </section>;
}
