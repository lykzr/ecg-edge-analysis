"""中转记录与合计额度；供命令行和后台共用，不依赖界面或入口。"""
import csv
import io
import json
from pathlib import Path
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
        try:
            for name in ('capture.bin', 'adc.csv', 'normalized.csv', 'upload.log', 'usb_rx.log', 'controls.log', 'input.csv'):
                self.files[name] = (self.directory/name).open('xb')
            self.monitor = Monitor(ResultRecorder(self.directory/'results', self.budget))
            self.row('adc.csv', ['pc_index', 'ch1_code24', 'ch2_code24'])
            self.row('normalized.csv', ['seq', 'sample_int16'])
        except BaseException:
            for stream in self.files.values(): stream.close()
            if getattr(self, 'monitor', None) is not None and self.monitor.recorder is not None:
                for stream in self.monitor.recorder.files.values(): stream.close()
            raise

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

