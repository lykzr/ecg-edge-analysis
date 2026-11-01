"""将已关闭的完整采集记录交给分析队列，不使用有限显示缓存或厂商滤波列。"""
import csv
import io
import math
import json

from ecg_bridge_capture import NominalConverter
from app.services import records


def submit(manager, owner, identifier, *, standard_preprocess=None):
    snapshot = manager.snapshot(owner, identifier)
    if snapshot['active']:
        raise ValueError('请停止并等待完整采集文件关闭后分析')
    if snapshot['info'].get('error') or snapshot['capture_info'].get('error') or snapshot.get('persistence_error'):
        raise ValueError('采集或保存失败，不能把缺样记录作为连续输入分析')
    kind = snapshot['kind']
    if kind not in {'vendor_csv', 'vendor_serial', 'bridge_csv', 'bridge_serial', 'standard500'}:
        raise ValueError('此模式没有可确认的完整500Hz采集输入；演示、日志、360Hz或只收结果不自动分类')
    if kind == 'standard500':
        if standard_preprocess not in {'hp05', 'raw'}:
            raise ValueError('标准500Hz输入须明确未滤波或已匹配高通；不猜测处理状态')
        filename = 'input.csv'
    else:
        if standard_preprocess is not None:
            raise ValueError('厂商原始CH2固定使用hp05，不允许绕过高通合同')
        filename = ('capture/' if kind.startswith('bridge_') else '') + 'samples.csv'
    path = manager.file(owner, identifier, filename)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('采集文件过大')
    samples = []
    first_time = None
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for index, row in enumerate(csv.DictReader(stream)):
            if index >= 200_000:
                raise ValueError('网页分析上限200000点；不会截断后冒充完整记录')
            if row.get('index') != str(index):
                raise ValueError('完整记录序号不连续，不补点或跳过坏行')
            if kind == 'standard500':
                if row.get('fs') != '500' or row.get('scale') != '4096':
                    raise ValueError('标准记录采样率或幅值比例不符')
                value = int(row['sample'])
                if str(value) != row['sample'] or not -32768 <= value <= 32767:
                    raise ValueError('标准记录不是规范int16')
                samples.append(value / 4096)
            else:
                raw = int(row['ecg_raw'])
                time_s = float(row['time_s'])
                if first_time is None:
                    first_time = time_s
                if not 0 <= raw < 2**24 or not math.isfinite(time_s) or time_s < 0 or abs(time_s-first_time-index/500) > 1e-6:
                    raise ValueError('CH2原码或采样时间不符')
                samples.append(NominalConverter.millivolts(raw - 8388608))
    if not samples:
        raise ValueError('采集记录无样本')
    acquisition = dict(session_id=identifier, kind=kind, samples=len(samples),
                       model_execution='host_pc', source_drop_known=False)
    expected = snapshot['capture_info'].get('total')
    if expected is not None and expected != len(samples):
        raise ValueError('完整文件点数与采集合计不符')
    if kind.startswith('bridge_') or kind == 'standard500':
        info = snapshot['info']
        board_model=snapshot.get('board_model',False)
        counters=('source_samples','confirmed') if board_model else ('source_samples','confirmed','echoed')
        if not info.get('done') or any(info.get(key) != len(samples) for key in counters):
            raise ValueError('板卡会话未完整确认，或来源/确认/回显点数不一致')
        header = snapshot['result'].get('header') or {}
        if header.get('fs') != 500 or header.get('scale') != (1 if board_model else 4096):
            raise ValueError('板端会话头采样率或单位不符')
        positions = []
        if board_model:
            result=json.loads(manager.file(owner,identifier,'result.json').read_text(encoding='utf-8'))
            if str(result['session'])!=header['session'] or result['samples']!=len(samples) or result['model_sha256']!=info['model_sha256']:
                raise ValueError('板端模型完整结果身份不匹配')
            for row in result['events']:
                pos=int(row['position'])
                if not 0<=pos<len(samples) or (positions and pos<=positions[-1]['r_sample500']):raise ValueError('板端模型事件时轴不符')
                positions.append(dict(event_id=row['beat_id'],r_sample500=pos))
            acquisition.update(board_model_sha256=result['model_sha256'],board_execution=result.get('execution_location','zynq_arm'),board_waveform_echoed=False,
                               board_performance=result.get('performance'),board_precision=result.get('precision','float64'))
        else:
            events_path = manager.file(owner, identifier, 'results/events.csv')
            with events_path.open(encoding='utf-8-sig', newline='') as stream:
                for row in csv.DictReader(stream):
                    pos = int(row['rpos'])
                    if row['session'] != header.get('session') or not 0 <= pos < len(samples) or (positions and pos <= positions[-1]['r_sample500']):
                        raise ValueError('板端事件时轴或会话不一致')
                    positions.append(dict(event_id=int(row['evt']), r_sample500=pos))
        acquisition.update(board_events=positions, board_session=header.get('session'),
                           board_result=snapshot['result'].get('cls'), board_confirmed=True)
    signal = dict(samples=samples, sample_rate_hz=500, unit='mV', lead='CH2' if kind != 'standard500' else 'single_lead',
                  source='live_'+kind, source_session_id=identifier,
                  model_preprocess=standard_preprocess or 'hp05', acquisition=acquisition)
    # 原始采集仍由会话文件保留；此CSV精确表示提交模型的整段mV输入。
    text = io.StringIO(newline='')
    writer = csv.writer(text, lineterminator='\n')
    writer.writerow(['mv'])
    writer.writerows([value] for value in samples)
    # 沿用本地账号、输入及代码/配置指纹；不能用静态会话键复用不同处理版本。
    return records.submit_analysis(owner, signal, raw_content=text.getvalue().encode())
