"""界面中转后台：独占Zynq串口，独立采集后台拥有来源，Tk只读有界快照。"""
from pathlib import Path
import queue
import threading
import time
import uuid

from ecg_bridge_records import BridgeRecords
from ecg_bridge_core import BridgeClient
from ecg_bridge_serial import DuplexSerial
from ecg_capture_core import CaptureWorker
from ecg_serial import WindowsSerial


class BridgeWorker(threading.Thread):
    def __init__(self, kind, source, zynq_port, directory, *, shift=8, sample_limit=None,
                 zynq_device=None, source_device=None, maximum=64*1024*1024,
                 port_factory=DuplexSerial, source_factory=WindowsSerial,
                 realtime=True, clock=time.monotonic, pause=.001):
        super().__init__(name='ecg-bridge', daemon=False)
        if kind not in ('csv', 'serial'):
            raise ValueError('来源须为厂商CSV或采集串口')
        if kind == 'serial' and str(source).upper() == zynq_port.upper():
            raise ValueError('采集与Zynq必须使用不同端口')
        if maximum < 4096:
            raise ValueError('中转合计记录额度至少4096字节')
        self.kind, self.source, self.port_name = kind, str(source), zynq_port
        self.directory = Path(directory); self.maximum = maximum
        self.port_factory, self.clock, self.pause = port_factory, clock, pause
        self.cancel = threading.Event(); self.lock = threading.Lock()
        self.queue = queue.Queue(maxsize=2048)
        self.info = dict(state='starting', reason=None, error=None, source_end=None,
                         source_samples=0, confirmed=0, echoed=0, done=False,
                         zynq_port=zynq_port, zynq_device=dict(zynq_device or {}),
                         source_device=dict(source_device or {}), source='REPLAY' if kind == 'csv' else 'ADC',
                         sample_rate_hz=500, shift=shift, sample_limit=sample_limit,
                         upstream_source_drop=None, board_validated=False,
                         output_dir=str(directory), source_status='未连接', result_status='未连接',
                         source_queue_peak=0, index_mapping='source_index = upload_seq = result_index; CSV time = csv_first_time_s + index/500')
        self.result = ((), (), None)
        self.capture = CaptureWorker(kind, source, self.directory/'capture', shift=shift,
                                     maximum=maximum//2, serial_factory=source_factory,
                                     realtime=realtime, clock=clock, device_info=source_device,
                                     on_sample=self.enqueue, sample_limit=sample_limit)

    def enqueue(self, sample, value):
        try:
            self.queue.put_nowait(value)
            with self.lock:
                self.info['source_queue_peak'] = max(self.info['source_queue_peak'], self.queue.qsize())
        except queue.Full as exc:
            raise BufferError('采集→中转队列已满；停止保留原码，不静默丢点') from exc

    def update(self, **values):
        with self.lock:
            self.info.update(values)

    def snapshot(self):
        with self.lock:
            info, result = dict(self.info), self.result
        capture_info, samples = self.capture.snapshot()
        return info, capture_info, samples, result

    def stop(self):
        self.cancel.set(); self.capture.stop()

    def run(self):
        records = port = client = None
        capture_started = False
        reason, error = 'failed', None
        try:
            records = BridgeRecords(self.directory, self.maximum-self.maximum//2)
            self.update(state='connecting', result_status='正在打开USB_UART')
            port = self.port_factory(self.port_name, 115200)
            client = BridgeClient(port, records.monitor, uuid.uuid4().hex, self.info['source'],
                                  clock=self.clock, write_log=records.write)
            while not client.done:
                # 等READY后再开源；每条连接只由一个后台持有，不由Tk抢读。
                if not capture_started and client.started and client.waiting is None:
                    if self.cancel.is_set():
                        reason = 'stopped_by_user'; break
                    self.capture.start(); capture_started = True
                    self.update(state='running', source_status='来源已启动', result_status='会话已确认')
                if self.cancel.is_set():
                    self.capture.stop()
                    self.update(state='draining', source_status='停止来源，正在收尾')
                    if not capture_started:
                        reason = 'stopped_by_user'; break
                source_info, _ = self.capture.snapshot()
                if source_info['error']:
                    raise OSError('来源停止：'+source_info['error'])
                values = []
                for _ in range(min(32, client.capacity-len(client.queue))):
                    try:
                        values.append(self.queue.get_nowait())
                    except queue.Empty:
                        break
                if values:
                    client.add(values)
                    first = client.received-len(values)
                    for i, value in enumerate(values):
                        records.row('normalized.csv', [first+i, value])
                if capture_started and not self.capture.is_alive() and self.queue.empty() and not client.eof:
                    self.update(source_end=source_info['reason'], source_status='来源结束，等待板端完成')
                    client.finish_source()
                client.pump()
                with self.lock:
                    self.info.update(client.summary())
                    self.info['queue_pending'] = self.queue.qsize()
                    self.result = (tuple(records.monitor.samples), tuple(records.monitor.events), records.monitor.header)
                # Windows Event.wait(1ms)可能按系统时钟片量化；sleep使用Python的高精度等待。
                # 仅后台短暂让出CPU，停止状态在下一轮检查，不阻塞Tk。
                time.sleep(self.pause)
            if client.done:
                if client.lines:
                    raise ValueError('结束后仍有USB残行')
                reason = 'stopped_by_user' if self.cancel.is_set() else 'completed'
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        finally:
            self.capture.stop()
            if capture_started:
                self.capture.join()
            capture_info, _ = self.capture.snapshot()
            if capture_info['error'] and error is None:
                reason, error = 'failed', '来源停止：'+capture_info['error']
            if client:
                self.update(**client.summary())
            if port is not None:
                try:
                    port.close()
                except Exception as exc:
                    reason, error = 'failed', (error or '')+'; 关闭USB_UART失败：'+str(exc)
            self.update(reason=reason, error=error, state='error' if error else 'stopped',
                        source_status='来源已关闭', result_status='USB_UART已关闭',
                        clipped=capture_info['clipped'], source_record=capture_info,
                        close_note='手动停止已保留部分会话；重新运行前需重新Run板端并配置PL' if reason == 'stopped_by_user' else '')
            if records is not None:
                try:
                    records.close(self.snapshot()[0])
                except Exception as exc:
                    self.update(reason='failed', state='error', error=(error or '')+'; 保存摘要失败：'+str(exc))
