"""采集/厂商CSV核心：双通道原码、独立记录和有界显示；不生成板端协议或检测结果。"""
from collections import deque
import argparse
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import threading
import time

from ecg_bridge_capture import VendorFrames, InputConverter
from ecg_monitor_core import RecordingLimitError
from ecg_serial import WindowsSerial

FIELDS = ['timestamp(s)', 'resp_raw', 'ecg_raw', 'resp_filtered', 'ecg_filtered']
RATE = 500


@dataclass(frozen=True)
class CaptureSample:
    index: int
    time_s: float
    resp_raw: int
    ecg_raw: int
    resp_filtered: float | None = None
    ecg_filtered: float | None = None

    @property
    def pair(self):
        return self.resp_raw - 8388608, self.ecg_raw - 8388608


class VendorCsv:
    """严格读取五列RawData，时间连续性仅代表文件；逐行保留原始字节。"""
    def __init__(self, path, retain=lambda data: None):
        self.path = Path(path)
        self.stream = self.path.open('rb')
        self.retain = retain
        self.index = 0
        self.first_time = None
        self.digest = hashlib.sha256()
        self.eof = False
        try:
            if self._row() != FIELDS:
                raise ValueError('须选择五列RawData波形CSV；HeatData参数摘要不是波形')
        except BaseException:
            self.close()
            raise

    def _row(self):
        raw = self.stream.readline(4097)
        if not raw:
            self.eof = True
            return None
        self.retain(raw); self.digest.update(raw)
        if len(raw) > 4096:
            raise ValueError('CSV单行超过4096字节')
        try:
            rows = list(csv.reader([raw.decode('utf-8-sig')], strict=True))
        except (UnicodeError, csv.Error) as error:
            raise ValueError('CSV编码或引号格式错误') from error
        if len(rows) != 1:
            raise ValueError('CSV不接受空行或跨行字段')
        return rows[0]

    def read(self):
        row = self._row()
        if row is None:
            if not self.index:
                raise ValueError('CSV没有波形数据')
            return None
        if len(row) != 5:
            raise ValueError(f'CSV第{self.index + 2}行须有五列')
        try:
            t, resp_f, ecg_f = float(row[0]), float(row[3]), float(row[4])
            resp, ecg = int(row[1]), int(row[2])
        except ValueError as error:
            raise ValueError(f'CSV第{self.index + 2}行数值错误') from error
        if not all(math.isfinite(v) for v in (t, resp_f, ecg_f)) or t < 0:
            raise ValueError('CSV存在非有限数值或负时间')
        if not 0 <= resp <= 0xFFFFFF or not 0 <= ecg <= 0xFFFFFF:
            raise ValueError('CSV原始列须为24位偏移码')
        if self.first_time is None:
            self.first_time = t
        if abs(t - self.first_time - self.index / RATE) > 1e-6:
            raise ValueError('CSV时间不符合连续500Hz软件时间轴；不补点或压紧缺口')
        sample = CaptureSample(self.index, t, resp, ecg, resp_f, ecg_f)
        self.index += 1
        return sample

    def close(self):
        self.stream.close()


class InitialFrames:
    """只在开始时寻找连续三帧合法候选；锁定后错误即停止，不自动重同步。"""
    def __init__(self):
        self.buffer = bytearray()
        self.parser = VendorFrames('document_34')
        self.locked = False
        self.skipped = 0

    def feed(self, data):
        if len(data) > 4096:
            raise ValueError('单次串口数据超过4096字节')
        if self.locked:
            return self.parser.feed(data)
        self.buffer.extend(data)
        if len(self.buffer) > 8192:
            raise ValueError('起始候选对齐缓存超限')
        candidates = []
        for start in range(len(self.buffer) - 101):
            if self.buffer[start:start + 2] != b'\xaa\xbb':
                continue
            try:
                probe = VendorFrames('document_34')
                probe.feed(self.buffer[start:start + 102])
            except ValueError:
                continue
            candidates.append(start)
        # 同一34字节周期的后续帧不是独立候选；不同相位则停止，不能猜。
        phases = {v % 34 for v in candidates}
        if len(phases) > 1:
            raise ValueError('起始帧存在多个候选相位，无法确定边界')
        if candidates:
            self.skipped = candidates[0]
            self.locked = True
            pending = bytes(self.buffer[self.skipped:]); self.buffer.clear()
            values = []
            for i in range(0, len(pending), 4096):
                values.extend(self.parser.feed(pending[i:i + 4096]))
            return values
        if len(self.buffer) >= 4096:
            raise ValueError('未找到连续三帧34字节候选；核对固件、格式和数据')
        return []

    @property
    def pending(self):
        return len(self.parser.buffer) if self.locked else len(self.buffer)


class CaptureRecorder:
    def __init__(self, directory, maximum):
        if maximum < 1024:
            raise ValueError('记录限额至少1024字节')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.maximum, self.used = maximum, 0
        self.files = {}
        try:
            for n in ('source.csv', 'capture.bin', 'samples.csv', 'normalized.csv'):
                self.files[n] = (self.directory / n).open('xb')
            self.row('samples.csv', ['index', 'time_s', 'resp_raw', 'ecg_raw', 'resp_code24',
                                    'ecg_code24', 'resp_filtered', 'ecg_filtered'])
            self.row('normalized.csv', ['index', 'sample'])
        except BaseException:
            for stream in self.files.values():
                stream.close()
            raise

    def write(self, name, data):
        if self.used + len(data) > self.maximum:
            raise RecordingLimitError('采集原文/解码记录达到总限额，停止并保留现场')
        self.files[name].write(data); self.used += len(data)

    def row(self, name, values):
        s = io.StringIO(newline='')
        csv.writer(s, lineterminator='\n').writerow(values)
        self.write(name, s.getvalue().encode('utf-8'))

    def sample(self, sample, normalized):
        self.row('samples.csv', [sample.index, sample.time_s, sample.resp_raw, sample.ecg_raw,
                                *sample.pair, sample.resp_filtered, sample.ecg_filtered])
        self.row('normalized.csv', [sample.index, normalized])

    def flush(self):
        for stream in self.files.values():
            stream.flush()

    def close(self, summary):
        errors = []
        for stream in self.files.values():
            try:
                stream.close()
            except OSError as error:
                errors.append(str(error))
        summary.update(data_bytes=self.used, max_bytes=self.maximum, close_errors=errors)
        with (self.directory / 'summary.json').open('x', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        if errors:
            raise OSError('; '.join(errors))


class CaptureWorker(threading.Thread):
    """后台独占一个来源，完整写盘；GUI仅取有界快照，不参与串口读取。"""
    def __init__(self, kind, source, directory, *, shift=8, maximum=64*1024*1024,
                 serial_factory=WindowsSerial, realtime=True, clock=time.monotonic, device_info=None,
                 on_sample=None, sample_limit=None):
        super().__init__(name='ecg-capture', daemon=False)
        if kind not in ('csv', 'serial'):
            raise ValueError('采集来源须为csv或serial')
        self.kind, self.source, self.directory = kind, str(source), Path(directory)
        self.converter = InputConverter(2, shift)
        self.maximum, self.factory, self.realtime, self.clock = maximum, serial_factory, realtime, clock
        if sample_limit is not None and (type(sample_limit) is not int or not 1 <= sample_limit <= 1800000):
            raise ValueError('采集点数上限须为1..1800000或留空')
        self.on_sample, self.sample_limit = on_sample, sample_limit
        self.cancel = threading.Event(); self.lock = threading.Lock()
        self.samples = deque(maxlen=4096)
        self.info = dict(kind=kind, source=self.source, rate_hz=RATE, rate_measured=False,
                         ecg_channel=2, resp_channel=1, shift=shift, unit='ADC code, uncalibrated',
                         total=0, received_bytes=0, state='starting', reason=None,
                         error=None, last_data=None, source_drop=None, initial_bytes_skipped=0,
                         alignment='csv_rows' if kind == 'csv' else 'not_locked', pending_bytes=0,
                         csv_complete=False, clipped=0, output_dir=str(directory),
                         device_info=dict(device_info or {}), source_read_to_eof=False)
        self.info.update(profile='vendor_v2.1.2_document34', firmware_verified=False)

    def set_info(self, **values):
        with self.lock:
            self.info.update(values)

    def snapshot(self):
        with self.lock:
            return dict(self.info), tuple(self.samples)

    def stop(self):
        self.cancel.set()

    def accept(self, sample, recorder):
        value = self.converter.convert(sample.pair)
        recorder.sample(sample, value)
        with self.lock:
            self.samples.append(sample)
            self.info.update(total=sample.index + 1, clipped=self.converter.clipped,
                             last_data=self.clock(), state='running')
        if self.on_sample:
            self.on_sample(sample, value)
        if self.sample_limit is not None and sample.index + 1 == self.sample_limit:
            self.cancel.set()
            self.set_info(reason='sample_limit')

    def run(self):
        recorder = reader = digest = None
        reason, error = 'stopped_by_user', None
        try:
            recorder = CaptureRecorder(self.directory, self.maximum)
            self.set_info(state='waiting')
            if self.kind == 'csv':
                reader = VendorCsv(self.source, lambda b: recorder.write('source.csv', b))
                started = self.clock()
                while not self.cancel.is_set():
                    sample = reader.read()
                    if sample is None:
                        reason = 'completed'; self.set_info(csv_complete=True)
                        break
                    if self.realtime and self.cancel.wait(max(0, sample.index / RATE - (self.clock() - started))):
                        break
                    self.accept(sample, recorder)
                    if sample.index % 32 == 0:
                        recorder.flush()
                self.set_info(source_sha256_read=reader.digest.hexdigest(),
                              source_read_to_eof=reader.eof, csv_first_time_s=reader.first_time)
            else:
                reader = self.factory(self.source, 115200)
                frames = InitialFrames(); index = 0; first_bytes = None; digest = hashlib.sha256()
                while not self.cancel.is_set():
                    data = reader.read(4096)
                    if data:
                        if first_bytes is None:
                            first_bytes = self.clock()
                        with self.lock:
                            self.info['received_bytes'] += len(data)
                            self.info['last_data'] = self.clock()
                        recorder.write('capture.bin', data); digest.update(data)
                        try:
                            pairs = frames.feed(data)
                        finally:
                            self.set_info(initial_bytes_skipped=frames.skipped, pending_bytes=frames.pending,
                                          alignment='candidate_3_frames_no_crc' if frames.locked else 'not_locked')
                        for resp, ecg in pairs:
                            if self.cancel.is_set():
                                break
                            self.accept(CaptureSample(index, index / RATE, resp + 8388608, ecg + 8388608), recorder)
                            index += 1
                        recorder.flush()
                    elif not frames.locked and first_bytes is not None and self.clock() - first_bytes > 5:
                        raise TimeoutError('五秒内未建立起始候选边界；停止，不丢字节重同步')
                    else:
                        self.cancel.wait(.005)
        except Exception as exc:
            reason, error = 'input_or_record_error', f'{type(exc).__name__}: {exc}'
        finally:
            if error is None and self.snapshot()[0]['reason'] == 'sample_limit':
                reason = 'sample_limit'
            if digest is not None:
                self.set_info(capture_sha256=digest.hexdigest())
            if reader is not None:
                try:
                    reader.close()
                except Exception as exc:
                    reason, error = 'close_error', (error or '') + '; ' + str(exc)
            self.set_info(state='error' if error else 'stopped', reason=reason, error=error)
            if recorder is not None:
                try:
                    recorder.close(self.snapshot()[0])
                except Exception as exc:
                    self.set_info(state='error', reason='record_close_error', error=(error or '') + '; ' + str(exc))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--shift', type=int, default=8, choices=range(24))
    args = parser.parse_args()
    worker = CaptureWorker('csv', args.csv, args.output_dir, shift=args.shift, realtime=False)
    worker.start()
    try:
        while worker.is_alive():
            worker.join(.05)
    except KeyboardInterrupt:
        worker.stop(); worker.join()
    info, _ = worker.snapshot()
    print(json.dumps(info, ensure_ascii=False))
    return 2 if info['error'] else (0 if info['csv_complete'] else 130)


if __name__ == '__main__':
    raise SystemExit(main())
