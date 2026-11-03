"""网页适配层：复用现有采集/中转后台，不在网页进程另造检测算法。"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import os
import threading
import time
import uuid

from ecg_paths import ROOT
from ecg_monitor_core import Monitor, Recorder, demo_frames
from ecg_serial import SerialCapture
from ecg_capture_core import CaptureWorker
from ecg_bridge_capture import NominalConverter
from ecg_bridge_worker import BridgeWorker
from ecg_runtime_worker import RuntimeWorker
from ecg_hgb_worker import HgbWorker
from ecg_ports import enumerate_ports, remembered_identity, select_port, validate_port, remember_identity
from ecg_uart import CLASS


class MonitorWorker(threading.Thread):
    """演示/原日志/只收串口共用记录器；锁仅保护解析和有限快照。"""
    def __init__(self, kind, source, directory, *, seconds=10, realtime=True, serial_factory=None):
        super().__init__(name='ecg-web-monitor', daemon=False)
        self.kind, self.source, self.directory = kind, source, Path(directory)
        self.seconds, self.realtime, self.serial_factory = seconds, realtime, serial_factory
        self.cancel = threading.Event()
        self.lock = threading.RLock()
        self.monitor = Monitor()
        self.info = dict(state='starting', error=None, reason=None, received_bytes=0)

    def stop(self):
        self.cancel.set()

    def run(self):
        connection = None
        reason = 'completed'
        try:
            self.monitor.recorder = Recorder(self.directory)
            with self.lock:
                self.info['state'] = 'running'
            if self.kind == 'result_serial':
                options = {} if self.serial_factory is None else {'factory': self.serial_factory}
                connection = SerialCapture(self.monitor, self.source, **options)
                last = time.monotonic()
                while not self.cancel.is_set():
                    with self.lock:
                        size = connection.poll()
                        self.info.update(received_bytes=self.monitor.input_info['received_bytes'],
                                         state='running' if size else self.info['state'])
                    if size:
                        last = time.monotonic()
                    elif time.monotonic() - last > 2:
                        with self.lock:
                            self.info['state'] = 'waiting'
                    self.cancel.wait(.01)
            elif self.kind == 'demo':
                start = time.monotonic()
                for at, data in demo_frames(seconds=self.seconds):
                    if self.realtime and self.cancel.wait(max(0, start + at - time.monotonic())):
                        break
                    if self.cancel.is_set():
                        break
                    with self.lock:
                        self.monitor.feed(data)
            else:
                # 原日志按块回放；不把读取时刻当采样时间。
                with Path(self.source).open('rb') as stream:
                    while not self.cancel.is_set():
                        data = stream.read(4096)
                        if not data:
                            break
                        with self.lock:
                            self.monitor.feed(data)
                        if self.realtime:
                            self.cancel.wait(.01)
            if self.cancel.is_set():
                reason = 'stopped_by_user'
        except Exception as exc:
            reason = 'error'
            with self.lock:
                self.info['error'] = str(exc)
        finally:
            try:
                if connection:
                    connection.close()
            except Exception as exc:
                self.info['error'] = str(exc)
            try:
                with self.lock:
                    self.monitor.finish(reason)
            except Exception as exc:
                self.info['error'] = str(exc)
            with self.lock:
                self.info.update(state='error' if self.info['error'] else 'stopped', reason=reason)

    def snapshot(self):
        with self.lock:
            monitor = self.monitor
            return dict(self.info), dict(monitor.counts), (tuple(monitor.samples), tuple(monitor.events), monitor.header), monitor.summary('snapshot')


def result_view(result):
    samples, events, header = result
    h = asdict(header) if header else None
    indexes = {seq: index for seq, index, _, _ in samples}
    points = [dict(seq=seq, index=index, raw=raw, filt=filt) for seq, index, raw, filt in samples]
    # 与原监视器一致：只给实际收到的位置标记，不猜测回绕或缺口。
    rows = [dict(asdict(event), index=indexes.get(event.pos)) for event in events]
    last = events[-1] if events else None
    classified = bool(header and header.caps & CLASS)
    return dict(header=h, samples=points, events=rows,
                hr=last.hr if last else None,
                rr_ms=last.rr * 1000 / header.fs if last and last.rr and header and header.fs else None,
                cls=(last.cls if last and last.cls != '?' else '未知') if classified else '未提供')


class LiveManager:
    """单进程独占硬件；历史落盘，浏览器断开不丢记录；上传与显示均有上限。"""
    KINDS = {'demo', 'log', 'result_serial', 'vendor_csv', 'vendor_serial',
             'bridge_csv', 'bridge_serial', 'standard360', 'standard500'}
    MAX_UPLOAD = 32 * 1024 * 1024

    def __init__(self, directory=None, *, port_enumerator=enumerate_ports, worker_factory=None):
        self.directory = Path(directory or ROOT / 'tmp/web_runtime/live')
        self.port_enumerator, self.worker_factory = port_enumerator, worker_factory
        self.lock = threading.RLock()
        self.jobs = {}
        self.uploads = {}
        self.owner_directory = None
        self.closing = False

    def _base(self, owner):
        return Path(self.owner_directory(owner)) if self.owner_directory else self.directory

    def _session_dir(self, owner, identifier):
        job = self.jobs.get(identifier)
        if job and job['owner'] == owner:
            return job['directory']
        current = self._base(owner) / 'sessions' / identifier
        return current if (current / 'web_session.json').exists() else self.directory / 'sessions' / identifier

    def reopen(self):
        with self.lock:
            if any(job['worker'].is_alive() for job in self.jobs.values()):
                raise RuntimeError('旧会话仍在关闭，不能重复启动服务')
            self.closing = False

    def ports(self):
        ports, warnings = self.port_enumerator()
        board = select_port(ports, identity=remembered_identity('zynq'))
        return dict(ports=ports, warnings=warnings,
                    zynq=board,
                    capture=select_port(ports, identity=remembered_identity('capture'), excluded=board))

    def upload(self, owner, name, content):
        if not content or len(content) > self.MAX_UPLOAD:
            raise ValueError('输入文件须为1字节至32MiB')
        suffix = Path(name or '').suffix.lower()
        if suffix not in {'.csv', '.log'}:
            raise ValueError('仅支持CSV或原始raw.log')
        with self.lock:
            upload_dir = self._base(owner) / 'uploads'
            existing = list(upload_dir.glob('*')) if upload_dir.exists() else []
            if len(existing) >= 64 or sum(p.stat().st_size for p in existing if p.is_file()) + len(content) > 256 * 1024 * 1024:
                raise ValueError('网页上传累计达到256MiB或64个文件，请先整理本机tmp/web_runtime/live/uploads')
            identifier = uuid.uuid4().hex
            path = upload_dir / (identifier + suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(content)
            self.uploads[identifier] = (owner, path)
            return dict(id=identifier, name=Path(name).name, bytes=len(content))

    def _source(self, owner, identifier, kind):
        item = self.uploads.get(identifier)
        if not item or item[0] != owner:
            raise LookupError('请重新上传自己的输入文件；服务重启后上传凭证失效')
        if item[1].suffix != ('.log' if kind == 'log' else '.csv'):
            raise ValueError('文件类型与运行方式不匹配')
        return item[1]

    def _port(self, config, key, ports, excluded=''):
        name = str(config.get(key, '')).upper()
        identity = str(config.get(key + '_identity', ''))
        # 浏览器必须带刷新时看到的身份，防止同COM换了另一块USB设备。
        if not identity:
            raise ValueError('缺少USB设备身份，请刷新端口后重新选择')
        return validate_port(name, {'device_id': identity}, ports, excluded=excluded)

    def start(self, owner, config, *, on_complete=None):
        kind = config.get('kind')
        if kind not in self.KINDS:
            raise ValueError('不支持的运行方式')
        with self.lock:
            if self.closing:
                raise ValueError('服务正在停止')
            if any(job['worker'].is_alive() for job in self.jobs.values()):
                raise ValueError('已有实时会话占用，请先停止；网页和原客户端也不能共用串口')
            seconds = config.get('seconds', 10)
            if type(seconds) not in (int, float) or not 1 <= seconds <= 300:
                raise ValueError('演示时长须为1至300秒')
            limit = config.get('sample_limit', 5000)
            if type(limit) is not int or not 1 <= limit <= 1800000:
                raise ValueError('蓝牙点数须为1至1800000')
            realtime = config.get('realtime', True)
            if type(realtime) is not bool:
                raise ValueError('实时节拍须为布尔值')
            board_model=config.get('board_model',False)
            classifier=config.get('board_classifier','hgb')
            precision=config.get('board_precision','FP32')
            if precision not in ('FP32','W8A8') or (precision=='W8A8' and (not board_model or classifier!='cnn')):raise ValueError('INT8仅支持板端CNN')
            streaming=config.get('board_streaming',False)
            if type(streaming) is not bool or (streaming and (not board_model or classifier!='cnn')):raise ValueError('流式分类目前须选择板端CNN')
            if classifier not in ('hgb','cnn'):raise ValueError('板端分类器必须为hgb或cnn')
            if type(board_model) is not bool or (board_model and kind not in {'standard500','bridge_csv','bridge_serial'}):
                raise ValueError('板端模型仅支持500Hz标准或厂商送样')
            if board_model and config.get('standard_preprocess') not in ('hp05','raw') and kind=='standard500':
                raise ValueError('板端模型须声明标准500Hz预处理状态')
            if board_model and not streaming and kind=='bridge_serial' and limit>30000:raise ValueError('板端整段模型每段最多30000点')
            ports, _ = self.port_enumerator()
            zynq = capture = None
            if kind in {'result_serial', 'bridge_csv', 'bridge_serial', 'standard360', 'standard500'}:
                zynq = self._port(config, 'zynq_port', ports)
            if kind in {'vendor_serial', 'bridge_serial'}:
                capture = self._port(config, 'capture_port', ports, excluded=zynq['port'] if zynq else '')
            source = self._source(owner, config.get('upload_id'), kind) if kind in {'log', 'vendor_csv', 'bridge_csv', 'standard360', 'standard500'} else None
            identifier = uuid.uuid4().hex
            directory = self._base(owner) / 'sessions' / identifier
            if self.worker_factory:
                worker = self.worker_factory(kind, source, directory, config)
            elif board_model:
                selected_worker=HgbWorker
                if streaming:
                    from ecg_cnn_live import CnnLiveWorker
                    selected_worker=CnnLiveWorker
                worker=selected_worker(kind,capture['port'] if capture else source,zynq['port'],directory,
                    preprocess=config.get('standard_preprocess'),sample_limit=limit,realtime=realtime,
                    zynq_device=zynq,source_device=capture,classifier=classifier,precision=precision)
            elif kind in {'demo', 'log', 'result_serial'}:
                worker = MonitorWorker(kind, zynq['port'] if zynq else source, directory,
                                       seconds=seconds, realtime=realtime)
            elif kind.startswith('vendor_'):
                worker = CaptureWorker('serial' if capture else 'csv', capture['port'] if capture else source,
                                       directory, realtime=realtime, device_info=capture,
                                       sample_limit=limit if capture else None, normalization='nominal500')
            elif kind.startswith('bridge_'):
                worker = BridgeWorker('serial' if capture else 'csv', capture['port'] if capture else source,
                                      zynq['port'], directory, realtime=realtime, zynq_device=zynq,
                                      source_device=capture, sample_limit=limit if capture else None, profile='runtime500')
            else:
                worker = RuntimeWorker(source, zynq['port'], directory, zynq_device=zynq,
                                       realtime=realtime, sampling_hz=500 if kind == 'standard500' else 360)
            self.jobs[identifier] = dict(owner=owner, kind=kind, worker=worker, directory=directory,board_model=board_model,
                                         zynq=zynq, capture=capture, created=time.time(), on_complete=on_complete,
                                         analysis=dict(status='waiting', task_id=None, error=None) if on_complete else None)
            try:
                worker.start()
            except Exception:
                self.jobs.pop(identifier)
                raise
            watcher = threading.Thread(target=self._complete, args=(identifier,), daemon=True)
            self.jobs[identifier]['watcher'] = watcher
            watcher.start()
            # 只保留最近32个后台对象；历史快照仍可读。
            for old in list(self.jobs)[:-32]:
                if not self.jobs[old]['worker'].is_alive() and not self.jobs[old]['watcher'].is_alive():
                    self.jobs.pop(old)
            return dict(id=identifier, kind=kind)

    def _complete(self, identifier):
        with self.lock:
            job = self.jobs[identifier]
        job['worker'].join()
        if job.get('on_complete'):
            try:
                task = job['on_complete'](job['owner'], identifier)
                with self.lock:
                    job['analysis'] = dict(status='submitted', task_id=task['id'], error=None)
            except Exception as exc:
                with self.lock:
                    # 预期输入拒绝只含合同说明；其他内部错误不泄露本机路径。
                    job['analysis'] = dict(status='failed', task_id=None,
                        error=str(exc) if isinstance(exc, ValueError) else '分析提交失败；采集文件保留，可手动重试。')
        try:
            snapshot = self._snapshot(identifier, job)
            job['directory'].mkdir(parents=True, exist_ok=True)
            payload = dict(owner=job['owner'], snapshot=snapshot)
            temporary = job['directory'] / 'web_session.new'
            temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            temporary.replace(job['directory'] / 'web_session.json')
            # 列表不反复加载4096点完整波形；只读小型索引，详情按需读取。
            metadata = {key: snapshot[key] for key in ('id', 'kind', 'created', 'active', 'info')}
            temporary.write_text(json.dumps(dict(owner=job['owner'], metadata=metadata), ensure_ascii=False), encoding='utf-8')
            temporary.replace(job['directory'] / 'web_meta.json')
        except Exception as exc:
            # 落盘失败不伪装成功；仍保留内存状态，并向界面报告。
            job['persistence_error'] = str(exc)

    def _snapshot(self, identifier, job):
        kind, worker = job['kind'], job['worker']
        source = []
        board_model=job.get('board_model',False)
        if board_model:
            info,capture_info,source,view=worker.snapshot()
            source=list(source);diagnostics=dict(info)
        elif kind in {'demo', 'log', 'result_serial'}:
            info, capture_info, result, diagnostics = worker.snapshot()
        elif kind.startswith('vendor_'):
            info, samples = worker.snapshot()
            capture_info, diagnostics, result = dict(info), dict(info), ((), (), None)
            source = [asdict(sample) for sample in samples]
        else:
            info, capture_info, samples, result = worker.snapshot()
            diagnostics = dict(info)
            source = [asdict(sample) for sample in samples]
        # 来源电压只由未滤波CH2原码计算；不使用厂商滤波列，也不复用
        # 已去直流/量化的板端输入。标准CSV不是ADC偏移码，不能套此公式。
        if kind in {'vendor_csv', 'vendor_serial', 'bridge_csv', 'bridge_serial'}:
            for sample in source:
                sample['ecg_nominal_mv'] = NominalConverter.millivolts(sample['ecg_raw'] - 8388608)
        if not board_model:view = result_view(result)
        active = worker.is_alive()
        if active and info.get('state') in {'stopped', 'error'}:
            info['state'] = 'closing'
        # 身份在合法报文后才记住，单纯打开COM不算设备确认。
        if view['header'] and job['zynq'] and not job.get('zynq_remembered'):
            remember_identity('zynq', job['zynq'])
            job['zynq_remembered'] = True
        if source and job['capture'] and not job.get('capture_remembered'):
            remember_identity('capture', job['capture'])
            job['capture_remembered'] = True
        files = []
        if not active and job['directory'].exists():
            files = [p.relative_to(job['directory']).as_posix() for p in job['directory'].rglob('*')
                     if p.is_file() and not p.is_symlink() and p.suffix in {'.log', '.csv', '.json', '.jsonl', '.bin'} and p.name not in {'web_session.json', 'web_meta.json'}]
        return dict(id=identifier, kind=kind, created=job['created'], active=active,
                    info=info, capture_info=capture_info, source_samples=source, result=view,
                    diagnostics=diagnostics, files=files, persistence_error=job.get('persistence_error'),
                    analysis=job.get('analysis'),
                    source_unit='int16 / 4096单位每mV' if kind.startswith('standard') else '未标定ADC原码',
                    board_model=board_model,
                    scope='SYNTH预设标记' if kind == 'demo' else '日志接收回放' if kind == 'log' else '收到的设备数据；不代表本次实物已验收')

    def _get(self, owner, identifier):
        if len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
            raise LookupError('会话不存在')
        job = self.jobs.get(identifier)
        if job and job['owner'] == owner:
            return job
        path = self._session_dir(owner, identifier) / 'web_session.json'
        if not path.exists():
            raise LookupError('会话不存在')
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['owner'] != owner:
            raise LookupError('会话不存在')
        return data['snapshot']

    def snapshot(self, owner, identifier):
        with self.lock:
            job = self._get(owner, identifier)
            return self._snapshot(identifier, job) if 'worker' in job else job

    def history(self, owner):
        rows = []
        with self.lock:
            for identifier, job in self.jobs.items():
                if job['owner'] == owner:
                    snapshot = self._snapshot(identifier, job)
                    rows.append({key: snapshot[key] for key in ('id', 'kind', 'created', 'active', 'info')})
            known = set(self.jobs)
        folders = set((self.directory / 'sessions').glob('*')) | set((self._base(owner) / 'sessions').glob('*'))
        if folders:
            for folder in folders:
                if folder.name in known or not folder.is_dir() or folder.is_symlink():
                    continue
                try:
                    payload = json.loads((folder / 'web_meta.json').read_text(encoding='utf-8'))
                    if payload['owner'] == owner:
                        if not any(row['id'] == payload['metadata']['id'] for row in rows):
                            rows.append(payload['metadata'])
                        rows = sorted(rows, key=lambda row: row['created'], reverse=True)[:100]
                except (OSError, ValueError, KeyError):
                    continue
        return sorted(rows, key=lambda row: row['created'], reverse=True)[:100]

    def stop(self, owner, identifier):
        with self.lock:
            job = self._get(owner, identifier)
            if 'worker' in job:
                job['worker'].stop()
        # 有界等待；未关闭时继续保持独占，不能立即启动第二个后台。
        if 'worker' in job:
            job['worker'].join(timeout=3)
        return self.snapshot(owner, identifier)

    def file(self, owner, identifier, name):
        snapshot = self.snapshot(owner, identifier)
        if snapshot['active']:
            raise ValueError('请停止并等待文件关闭后再下载')
        if name not in snapshot['files']:
            raise LookupError('记录文件不存在')
        base = self._session_dir(owner, identifier).resolve()
        path = (base / name).resolve()
        if not path.is_relative_to(base) or path.is_symlink() or not path.is_file():
            raise LookupError('记录文件不存在')
        return path

    def svg(self, owner, identifier):
        from collections import deque
        from ecg_uart import Header, Event
        from ui.plot import plot_geometry
        from html import escape
        snapshot = self.snapshot(owner, identifier)
        view = snapshot['result']
        monitor = Monitor()
        monitor.header = Header(**view['header']) if view['header'] else None
        monitor.samples = deque((row['seq'], row['index'], row['raw'], row['filt']) for row in view['samples'])
        monitor.events = deque(Event(**{key: value for key, value in row.items() if key in Event.__dataclass_fields__}) for row in view['events'])
        geometry = plot_geometry(monitor)
        title = '无数据' if not monitor.header else f'{monitor.header.source} / {monitor.header.detector}'
        parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 400">',
                 '<rect width="1000" height="400" fill="#101820"/>',
                 f'<text x="20" y="20" fill="white">{escape(title)}</text>']
        for key, color in [('raw', '#58d6a6'), ('filt', '#70baff')]:
            for segment in geometry[key]:
                points = ' '.join(f'{x:.2f},{y:.2f}' for x, y in segment)
                parts.append(f'<polyline points="{points}" fill="none" stroke="{color}"/>')
        for x, _ in geometry['events']:
            parts.append(f'<line x1="{x:.2f}" x2="{x:.2f}" y1="30" y2="318" stroke="#ffcd70"/>')
        parts.append(f'<text x="20" y="385" fill="white">{escape(geometry["unit"])} / {escape(snapshot["scope"])}</text></svg>')
        return '\n'.join(parts)

    def shutdown(self):
        with self.lock:
            self.closing = True
            workers = [job['worker'] for job in self.jobs.values() if job['worker'].is_alive()]
            for worker in workers:
                worker.stop()
        deadline = time.monotonic() + 5
        for worker in workers:
            worker.join(timeout=max(0, deadline - time.monotonic()))
        for job in list(self.jobs.values()):
            if 'watcher' in job:
                job['watcher'].join(timeout=max(0, deadline - time.monotonic()))


manager = LiveManager(os.environ.get('ECG_WEB_LIVE_DIR'))
