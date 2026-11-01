"""网页分类适配：固定研究模型、独立进程、逐拍输出；不将N译为健康。"""
from pathlib import Path
import json
import math
import os
import statistics
import subprocess
import sys
from bisect import bisect_left, bisect_right


def associate_board_events(beats, board_events):
    """固定±50ms且双向唯一才关联；保留双方位置，不拟合偏移或强配。"""
    model_positions = [b['r_sample500'] for b in beats]
    board_positions = [b['r_sample500'] for b in board_events]
    matched = 0
    for beat in beats:
        pos = beat['r_sample500']
        left, right = bisect_left(board_positions, pos-25), bisect_right(board_positions, pos+25)
        beat.update(board_event_id=None, board_r_sample500=None, board_delta_samples=None,
                    board_association='unmatched' if left == right else 'ambiguous')
        if right-left == 1:
            candidate = board_events[left]
            bp = candidate['r_sample500']
            if bisect_right(model_positions, bp+25)-bisect_left(model_positions, bp-25) == 1:
                beat.update(board_event_id=candidate['event_id'], board_r_sample500=bp,
                            board_delta_samples=pos-bp, board_association='matched')
                matched += 1
    return dict(tolerance_samples=25, sampling_hz=500, matched=matched,
                model_unmatched=len(beats)-matched, board_unmatched=len(board_events)-matched,
                scope='仅位置关联，不是专家检测准确率；板端类别不被覆盖')


class HgbClassifier:
    model_version = 'HGB-v92-fold0'

    def __init__(self, python=None):
        self.python = python or sys.executable

    def predict(self, processed):
        def unavailable(message):
            return dict(status='model_unavailable', label=None, confidence=None,
                        model_version=self.model_version, explanation=message,
                        task_type='beat_level', execution_location='host_pc', qualified=False)
        if processed.get('sample_rate_hz') != 500 or processed.get('unit') != 'mV':
            return unavailable('HGB要求500Hz单导联mV，不自动重采样或猜测单位。')
        samples = processed.get('waveform_raw_mV')
        if not isinstance(samples, list) or not 1 <= len(samples) <= 200_000:
            return unavailable('HGB网页入口要求完整连续记录，最多200000点，不截断后分类。')
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in samples):
            return unavailable('模型输入包含非有限数值。')
        preprocess = processed.get('model_preprocess', 'hp05')
        if preprocess not in {'hp05', 'raw'}:
            return unavailable('模型预处理协议未明确，拒绝猜测滤波状态。')
        worker = Path(__file__).with_name('hgb_worker.py')
        env = os.environ.copy()
        env.update({name: '4' for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS')})
        try:
            response = subprocess.run([self.python, '-I', '-X', 'utf8', '-B', str(worker)],
                input=json.dumps(dict(samples=samples, preprocess=preprocess), allow_nan=False).encode(),
                capture_output=True, timeout=180, env=env,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if response.returncode:
                return unavailable('HGB环境或文件校验失败；请用配置的模型Python运行check.py。')
            result = json.loads(response.stdout)
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return unavailable('HGB进程不可用或超时；未产生类别，不自动重试或改用其他模型。')
        # 单一摘要只描述心拍构成，不作整段节律诊断或多数投票。
        beats = result['beats']
        acquisition = processed.get('acquisition') or {}
        association = (associate_board_events(beats, acquisition['board_events'])
                       if 'board_events' in acquisition else None)
        counts = {label: sum(b['valid'] and b['label'] == label for b in beats) for label in ('N', 'S', 'VF')}
        valid = sum(counts.values())
        rr = [(b['r_sample500'] - a['r_sample500']) / 500 for a, b in zip(beats, beats[1:])]
        rates = [60 / value for value in rr if value > 0]
        summary = '仅检测到N类心拍' if counts['S'] + counts['VF'] == 0 else '检测到需复核的S/VF类心拍'
        if not valid:
            summary = None
        return dict(status='classified' if valid else 'no_valid_beats', label=summary,
            confidence=None, model_version=self.model_version, task_type='beat_level',
            execution_location='host_pc', qualified=False, model_sha256=result['model_sha256'],
            preprocess=preprocess, clipped_samples=result['clipped_samples'],
            classes=['N', 'S', 'VF'], VF_definition=result['VF_definition'],
            board_association=association,
            beats=dict(count=len(beats), classified_count=valid, unclassified_count=len(beats)-valid,
                       by_type=counts, items=beats),
            heart_rate=(dict(bpm=round(60/statistics.median(rr), 2),
                            min_bpm=round(min(rates), 2), max_bpm=round(max(rates), 2)) if rates else None),
            flags=[], intervals_ms=None,
            explanation='研究模型逐拍分类；N不表示健康，VF为V/E/F合并，不表示心室颤动。')
