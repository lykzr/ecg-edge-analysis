"""已知公开记录的自动切拍→开发权重→旧PC结果记录离线闭环；不操作串口。"""
import argparse
from collections import deque
from dataclasses import asdict
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'data'), str(ROOT/'src/reference'), str(ROOT/'src/pc'), str(ROOT/'src')]
from ecg_dataset import load_record, digest
from ecg_signal_pipeline import SignalPipeline
from ecg_classifier import ModelSpec, Request, Result, ClassQueue, prepare, event_line
from ecg_monitor_core import Monitor, Recorder
from ui.plot import save_svg


def run(raw, record, seconds, output, inference_python):
    protocol = json.loads((ROOT/'data/qrs_runtime_protocol.json').read_text())
    if record not in protocol['development_records'] + protocol['evaluation_records']:
        raise ValueError('只允许已有已知MIT记录，不读取独立患者')
    if seconds <= 0 or seconds > 1805:
        raise ValueError('接口回放时长无效')
    xs, _, meta = load_record(raw, record, 'MLII')
    xs = xs[:int(seconds*360)]
    output.mkdir(parents=True, exist_ok=False)
    stderr = (output/'backend_stderr.log').open('x', encoding='utf-8')
    process = subprocess.Popen([str(inference_python), '-B', str(ROOT/'src/reference/ecg_classifier.py'),
                                '--serve-development-fold', '0'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=stderr, text=True, bufsize=1,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    messages = queue.Queue(maxsize=8)
    def read():
        for line in process.stdout:
            messages.put(line)
        messages.put(None)
    threading.Thread(target=read, daemon=True).start()
    def reply(timeout=10):
        line = messages.get(timeout=timeout)
        if line is None:
            raise RuntimeError('本地推理子进程意外结束')
        value = json.loads(line)
        if 'error' in value:
            raise RuntimeError(value['error'])
        return value
    monitor = None
    try:
        ready = reply(60)
        spec = ModelSpec.from_dict(ready['spec'])
        session = 'softref-' + uuid.uuid4().hex[:12]
        model = SignalPipeline(360)
        jobs = ClassQueue(spec)
        jobs.reset(session)
        monitor = Monitor(Recorder(output/'pc'))
        monitor.input_info = {'kind': 'software_reference_development_model', 'accepted': False}
        monitor.feed(f'H,ECG-UART-1,softref-class-1,{session},REPLAY,QRS26-SOFT,360,4096,0x15\n'.encode())
        monitor.feed(f'L,W,DEV_MODEL_UNACCEPTED model={spec.model_id} weights={spec.weights_sha256}\n'.encode())
        monitor.feed(f'L,I,PREPROCESS sha256={spec.preprocess_sha256} norm={spec.normalization_sha256}\n'.encode())
        pending = deque()
        requests, results = [], []
        beat_id, wave_start, wave_buffer = 0, 0, []
        wall_start = time.monotonic()
        def now():
            return int((time.monotonic()-wall_start)*1000)
        def output_result(result):
            monitor.feed(event_line(result, spec))
            if not result.valid:
                monitor.feed(f'L,W,CLASS_STATE evt={result.request.beat_id} state={result.status}\n'.encode())
            results.append(asdict(result))
        def drain():
            while pending and pending[0]['request'] is not None:
                item = pending.popleft()
                req = item['request']
                if jobs.submit(req, now()) != 'ACCEPTED':
                    raise RuntimeError('分类队列BUSY，停止而非静默丢拍')
                work = jobs.take(now())
                if work is None:
                    expired = jobs.expire(now())
                    if expired is None:
                        raise RuntimeError('请求未能启动')
                    output_result(expired)
                    continue
                requests.append(asdict(work))
                process.stdin.write(json.dumps(asdict(work))+'\n')
                process.stdin.flush()
                value = reply()
                received = Result(Request.from_dict(value['request']), value['status'],
                                  value['class_id'], value['valid'], value['accepted'])
                output_result(jobs.complete(received, now()))
        for n, x in enumerate(xs):
            wave_buffer += [str(x), 'NA']
            if len(wave_buffer) == 16:
                monitor.feed((f'W,{wave_start},8,'+','.join(wave_buffer)+'\n').encode())
                wave_start += 8
                wave_buffer.clear()
            events, windows = model.push(x, sequence=n)
            for emitted, position, rr in events:
                beat_id += 1
                if len(pending) >= 32:
                    raise OverflowError('检测→窗口队列满')
                item = dict(id=beat_id, event=(emitted, position, rr), request=None)
                if position < model.cutter.before:
                    item['request'] = Request(session, beat_id, position, rr, 360, n, spec.model_id,
                        spec.weights_sha256, spec.preprocess_sha256, (), (), 'WINDOW_INCOMPLETE')
                pending.append(item)
            for beat in windows:
                target = next((item for item in pending if item['event'][1] == beat.position), None)
                if target is None:
                    raise RuntimeError('窗口没有对应检测事件')
                target['request'] = prepare(beat, session, target['id'], spec)
            drain()
        if wave_buffer:
            monitor.feed((f'W,{wave_start},{len(wave_buffer)//2},'+','.join(wave_buffer)+'\n').encode())
        pipeline = model.finish()
        for item in pending:
            if item['request'] is None:
                emitted, position, rr = item['event']
                item['request'] = Request(session, item['id'], position, rr, 360, len(xs)-1,
                    spec.model_id, spec.weights_sha256, spec.preprocess_sha256, (), (), 'WINDOW_INCOMPLETE')
        drain()
        monitor.feed(f'L,I,END reason=completed samples={len(xs)} events={beat_id}\n'.encode())
        summary = monitor.finish()
        save_svg(monitor, output/'pc/waveform.svg')
        for name, values in [('requests.jsonl', requests), ('results.jsonl', results)]:
            with (output/name).open('x', encoding='utf-8') as stream:
                for value in values:
                    stream.write(json.dumps(value)+'\n')
        report = dict(passed=True, record=record, input=meta, source_samples=len(xs),
                      events=beat_id, results=len(results), unknown=sum(not r['valid'] for r in results),
                      spec=asdict(spec), monitor=summary, pipeline=pipeline,
                      protocol='ECG-CLASS-1', scope='known-data software interface only; no accuracy/board claim',
                      board=False, wireless=False, trained=False)
        assert summary['counts']['samples'] == len(xs) and summary['counts']['events'] == beat_id == len(results)
        assert not any(summary['protocol_counts'].get(k,0) for k in ('invalid','overlong','non_protocol'))
        (output/'summary.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({k:report[k] for k in ('passed','events','results','unknown','scope')}))
    finally:
        try:
            process.stdin.close()
            process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            process.terminate()
            process.wait(timeout=5)
        stderr.close()
        if monitor is not None and monitor.recorder is not None and not monitor.recorder.closed:
            monitor.finish('failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, required=True)
    parser.add_argument('--record', default='100')
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--inference-python', type=Path, required=True)
    args = parser.parse_args()
    run(args.raw_dir,args.record,args.seconds,args.output_dir,args.inference_python)
