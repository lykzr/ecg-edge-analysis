"""独立电脑中转入口；不改变现有Tk监视器、不自动连接或复位板卡。"""
import argparse
import csv
import io
import json
from pathlib import Path
import time
import uuid

from ecg_bridge_core import BridgeClient
from ecg_bridge_capture import VendorFrames, InputConverter
from ecg_bridge_serial import DuplexSerial
from ecg_serial import WindowsSerial
from ecg_monitor_core import Monitor, Recorder


class Budget:
    def __init__(self, maximum):
        if maximum < 1024:
            raise ValueError('记录限额至少1024字节')
        self.maximum, self.used = maximum, 0

    def check(self, count):
        if self.used + count > self.maximum:
            raise OSError('中转记录达到总限额，停止保存现场')


class ResultRecorder(Recorder):
    def __init__(self, directory, budget):
        self.budget = budget
        super().__init__(directory, max_bytes=budget.maximum)

    def write(self, name, data):
        self.budget.check(len(data)); super().write(name, data)
        self.budget.used += len(data)


class BridgeRecords:
    def __init__(self, directory, maximum=64*1024*1024):
        self.budget = Budget(maximum)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.files = {}
        for name in ('capture.bin', 'adc.csv', 'normalized.csv', 'upload.log', 'usb_rx.log', 'controls.log', 'input.csv'):
            self.files[name] = (self.directory/name).open('xb')
        self.monitor = Monitor(ResultRecorder(self.directory/'results', self.budget))
        self.row('adc.csv', ['pc_index', 'ch1_code24', 'ch2_code24'])
        self.row('normalized.csv', ['seq', 'sample_int16'])

    def write(self, name, data):
        self.budget.check(len(data)); self.files[name].write(data); self.files[name].flush()
        self.budget.used += len(data)

    def row(self, name, values):
        buffer = io.StringIO(newline=''); csv.writer(buffer, lineterminator='\n').writerow(values)
        self.write(name, buffer.getvalue().encode('utf-8'))

    def close(self, summary):
        errors = []
        try:
            self.monitor.finish(summary['reason'])
        except OSError as error:
            errors.append(str(error))
        for stream in self.files.values():
            try:
                stream.close()
            except OSError as error:
                errors.append(str(error))
        summary.update(data_bytes=self.budget.used, close_errors=errors)
        (self.directory/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        if errors:
            raise OSError('; '.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--csv', type=Path, help='已转换int16 CSV，列名sample，可另有从0连续的index')
    group.add_argument('--vendor-log', type=Path, help='已确认从帧边界开始的厂商二进制原文')
    group.add_argument('--vendor-port', help='仅已确认串口透传的蓝牙虚拟COM；不代表支持任意BLE设备')
    parser.add_argument('--zynq-port', required=True)
    parser.add_argument('--format', choices=('source_10', 'document_34'))
    parser.add_argument('--channel', type=int, choices=(1, 2))
    parser.add_argument('--shift', type=int, choices=range(24))
    parser.add_argument('--aligned', action='store_true', help='明确确认厂商输入的起始帧边界')
    parser.add_argument('--source', choices=('ADC', 'REPLAY', 'SYNTH'), required=True)
    parser.add_argument('--rate', type=int, choices=(500,), required=True, help='显式声明源标称采样率；本版只接500Hz')
    parser.add_argument('--samples', type=int, help='实时采集须指定此次最多送入的点数')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--max-bytes', type=int, default=64*1024*1024)
    args = parser.parse_args()
    vendor = bool(args.vendor_log or args.vendor_port)
    if vendor and (not args.format or args.channel is None or args.shift is None or not args.aligned):
        parser.error('厂商输入须显式提供--format/--channel/--shift/--aligned')
    if args.csv and any(x is not None for x in (args.format, args.channel, args.shift)):
        parser.error('CSV已经是int16输入，不混用厂商通道/位移参数')
    if args.vendor_port and (args.samples is None or args.vendor_port.upper() == args.zynq_port.upper()):
        parser.error('采集COM与USB_UART COM必须不同；实时输入须指定--samples')
    if args.samples is not None and not 1 <= args.samples <= 1800000:
        parser.error('--samples须为1..1800000')
    if args.max_bytes < 1024:
        parser.error('--max-bytes至少1024')
    converter = InputConverter(args.channel, args.shift) if vendor else None
    framer = VendorFrames(args.format) if vendor else None
    records = BridgeRecords(args.output_dir, args.max_bytes)
    session = uuid.uuid4().hex
    port = source = client = None
    summary = dict(reason='failed', error=None, session=session, sample_rate_hz=500,
                   source=args.source, format=args.format, channel=args.channel, shift=args.shift,
                   upstream_source_sequence=False, board_validated=False)
    count = observed = 0
    try:
        if args.csv:
            with args.csv.open('rb') as original:
                while chunk := original.read(4096):
                    records.write('input.csv', chunk)
            source = (records.directory/'input.csv').open('r', encoding='utf-8-sig', newline='')
            rows = csv.DictReader(source)
            if not rows.fieldnames or 'sample' not in rows.fieldnames:
                raise ValueError('CSV缺少sample列')
        elif args.vendor_log:
            source = args.vendor_log.open('rb')
        else:
            source = WindowsSerial(args.vendor_port)
        port = DuplexSerial(args.zynq_port)
        client = BridgeClient(port, records.monitor, session, args.source, write_log=records.write)
        while not client.done:
            if not client.eof and (args.vendor_port or len(client.queue) < client.capacity-512):
                values = []; eof = False
                if args.csv:
                    for _ in range(32):
                        row = next(rows, None)
                        if row is None:
                            eof = True; break
                        value = int(row['sample'])
                        if str(value) != row['sample'] or not -32768 <= value <= 32767:
                            raise ValueError('CSV样本非规范int16')
                        if 'index' in row and row['index'] != str(observed):
                            raise ValueError('CSV index缺口或非0起点')
                        if 'fs' in row and row['fs'] != '500':
                            raise ValueError('CSV采样率不等于声明的500Hz')
                        observed += 1; values.append(value)
                else:
                    data = source.read(4096 if args.vendor_port else 320)
                    if data:
                        records.write('capture.bin', data)
                        for pair in framer.feed(data):
                            records.row('adc.csv', [observed, *pair]); observed += 1
                            if args.samples is None or count + len(values) < args.samples:
                                values.append(converter.convert(pair))
                    elif args.vendor_log:
                        framer.finish(); eof = True
                if args.samples is not None:
                    values = values[:max(0, args.samples-count)]
                for value in values:
                    records.row('normalized.csv', [count, value]); count += 1
                client.add(values)
                if eof and args.samples is not None and count < args.samples:
                    raise ValueError('源文件少于指定样本数，不能当完整运行成功')
                if eof or (args.samples is not None and count == args.samples):
                    summary['source_end'] = 'limit' if args.samples is not None and count == args.samples else 'eof'
                    client.finish_source()
            client.pump()
            time.sleep(.001)
        if client.lines:
            raise ValueError('结束后还有USB残行')
        summary.update(reason='completed', observed_points=observed, **client.summary())
    except (Exception, KeyboardInterrupt) as error:
        summary['error'] = f'{type(error).__name__}: {error}'
        if client:
            summary.update(client.summary())
    finally:
        summary.update(observed_points=observed, planned_points=count)
        summary['clipped'] = converter.clipped if converter else 0
        for handle in (source, port):
            if handle:
                try:
                    handle.close()
                except OSError as error:
                    summary.update(reason='failed', error=f'关闭连接失败：{error}')
        records.close(summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary['reason'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
