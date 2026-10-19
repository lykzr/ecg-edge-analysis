"""编译实际PS可移植C核心，注入假计时/AXI/UART，并由现有PC解析器核对。"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/pc'))
from ecg_monitor_core import Monitor


class StreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
        if not compiler:
            raise unittest.SkipTest('需要现有GCC；不自动安装')
        parent = ROOT/'tmp/ps_stream_tests'; parent.mkdir(parents=True, exist_ok=True)
        cls.directory = parent/uuid.uuid4().hex[:12]
        cls.directory.mkdir(exist_ok=False)
        cls.exe = cls.directory/'stream_host.exe'
        command = [compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT/'src/ps/ecg_stream'),
                   str(ROOT/'sim/stream_host.c'), str(ROOT/'src/ps/ecg_stream/stream.c'), '-o', str(cls.exe)]
        # 编译器临时文件放本项目独立目录，不依赖系统TEMP的写权限。
        environment = dict(os.environ, TMP=str(cls.directory), TEMP=str(cls.directory))
        result = subprocess.run(command, capture_output=True, timeout=60, env=environment)
        (cls.directory/'compile.log').write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace'))
        cls.legacy_exe = cls.directory/'stream_host_360.exe'
        command[-1] = str(cls.legacy_exe)
        command.insert(1, '-DECG_STREAM_RATE_HZ=360U')
        result = subprocess.run(command, capture_output=True, timeout=60, env=environment)
        (cls.directory/'compile_360.log').write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace'))

    def run_case(self, name, expected=0):
        result = subprocess.run([str(self.exe), name], capture_output=True, timeout=15)
        (self.directory/(name+'.log')).write_bytes(result.stdout)
        (self.directory/(name+'_result.txt')).write_bytes(result.stderr)
        self.assertEqual(result.returncode, expected, result.stderr.decode(errors='replace'))
        monitor = Monitor()
        for start in range(0, len(result.stdout), 7):
            monitor.feed(result.stdout[start:start+7])
        monitor.finish()
        self.assertEqual(monitor.decoder.counts['invalid'], 0, monitor.decoder.last_error)
        self.assertEqual(monitor.decoder.counts['truncated'], 0)
        self.assertEqual(monitor.decoder.counts['overlong'], 0)
        return monitor, result

    def test_rational_pacing_event_consumer_and_partial_tail(self):
        m, result = self.run_case('normal')
        self.assertEqual(m.counts['samples'], 5003)
        self.assertEqual(m.counts['events'], 10)
        self.assertEqual(m.counts['sessions'], 1)
        self.assertEqual(m.counts['wave_gap'], 0)
        self.assertEqual([e.pos for e in m.events], [70+500*i for i in range(10)])
        self.assertEqual([e.rr for e in m.events], [0]+[500]*9)
        self.assertEqual(m.status.source_drop, 0); self.assertEqual(m.status.tx_drop, 0)
        # PC对同一H幂等去重，因此核对线上的重发次数，不改解析器语义。
        self.assertGreater(result.stdout.count(b'H,ECG-UART-1,'), 1)
        self.assertIn(b'reason=completed', result.stdout)
        self.assertEqual(m.header.source, 'SYNTH'); self.assertIsNone(m.header.scale)
        self.assertEqual(m.header.fs, 500)
        self.assertIn(b'QRS-ORIG-60,500,-1,0xD', result.stdout)
        self.assertIn(b'T,-1,-1,?,NA,500,', result.stdout)
        self.assertEqual([e.hr for e in m.events][1:], [60.0]*9)
        self.assertTrue(all(e.cls == '?' for e in m.events))

    def test_short_run_does_not_pad_samples(self):
        m, _ = self.run_case('short')
        self.assertEqual(m.counts['samples'], 3)
        self.assertEqual(m.counts['events'], 0)

    def test_legacy_360_parameter_remains_independent(self):
        result = subprocess.run([str(self.legacy_exe), 'normal'], capture_output=True, timeout=15)
        (self.directory/'legacy_360.log').write_bytes(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        monitor = Monitor()
        monitor.feed(result.stdout); monitor.finish()
        self.assertEqual(monitor.decoder.counts['invalid'], 0)
        self.assertEqual(monitor.header.fs, 360)
        self.assertEqual(monitor.counts['samples'], 3603)
        self.assertEqual([e.pos for e in monitor.events], [79+360*i for i in range(10)])
        self.assertEqual([e.hr for e in monitor.events][1:], [60.0]*9)

    def test_slow_uart_drops_whole_wave_batches_and_counts_samples(self):
        m, result = self.run_case('slow')
        self.assertGreater(m.status.tx_drop, 0)
        self.assertEqual(m.status.source_drop, 0)
        self.assertEqual(m.counts['samples']+m.status.tx_drop, 5003)
        self.assertEqual(m.counts['events'], 10)
        self.assertIn('TX_DROP', m.status.flags)
        self.assertGreater(m.counts['wave_gap'], 0)
        # 最后一批也可能丢弃，PC仅凭序号看不到末尾缺口，须结合最终T/L。
        self.assertLessEqual(m.counts['wave_gap'], m.status.tx_drop)

    def test_deadline_miss_stops_without_catchup_burst(self):
        m, result = self.run_case('deadline', 2)
        self.assertEqual(m.counts['samples'], 20)
        self.assertIn(b'SAMPLE_DEADLINE_MISSED', result.stdout)

    def test_stalled_uart_terminates_with_failure(self):
        _, result = self.run_case('stalled', 2)
        self.assertIn(b'UART_STALLED', result.stderr)
        self.assertNotIn(b'reason=completed', result.stdout)

    def test_nonfresh_pl_and_wrong_config_refuse_samples(self):
        for name, reason in [('dirty', b'NEED_FRESH_PL'), ('config', b'CONFIG_MISMATCH')]:
            m, result = self.run_case(name, 2)
            self.assertEqual(m.counts['samples'], 0)
            self.assertIn(reason, result.stdout)

    def test_zero_event_values_do_not_mean_empty_fifo(self):
        m, result = self.run_case('zero_event')
        self.assertEqual(m.events[0].seq, 0); self.assertEqual(m.events[0].pos, 0)
        self.assertIn(b'pops=1', result.stderr)

    def test_invalid_contract_rejected(self):
        self.run_case('invalid')


if __name__ == '__main__':
    unittest.main()
