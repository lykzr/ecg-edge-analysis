"""启动学习/峰判决的静默、极性、幅值、暂停、复位与因果边界。"""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/reference'))
sys.path.insert(0,str(ROOT/'src/pc'))
from ecg_auto import AutoDetector
from ecg_reference import Config,Detector
from ecg_bridge_core import BridgeClient
from ecg_monitor_core import Monitor


def run(model,values):
    events=[]
    for value in values:
        s=model.tick(value)
        if s.qrs_valid:events.append((s.qrs_sample_index,s.rr_interval_samples))
    return events


class AutoChecks(unittest.TestCase):
    def test_explicit_protocol_identity_no_unlisted_detector(self):
        for identity in ('QRS-ORIG-60','QRS-AUTOPEAK-60'):
            monitor=Monitor();client=BridgeClient(None,monitor,'known','REPLAY')
            client._line(f'H,ECG-UART-1,ps-auto-1,known,REPLAY,{identity},500,-1,0xD\n'.encode())
            self.assertEqual(monitor.header.detector,identity)
        with self.assertRaises(ValueError):
            BridgeClient(None,Monitor(),'known','REPLAY')._line(b'H,ECG-UART-1,x,known,REPLAY,UNKNOWN,500,-1,0xD\n')

    def test_low_amplitude_and_polarity(self):
        for amplitude in (16,100,1000,20000):
            values=[0]*5003
            for i in range(100,5003,500):values[i]=amplitude if i//500%2==0 else -amplitude
            expected=[(1130+500*i,0 if i==0 else 500) for i in range(8)]
            self.assertEqual(run(AutoDetector(Config(sample_rate_hz=500)),values),expected)
            self.assertEqual(run(AutoDetector(Config(sample_rate_hz=500)),[-v for v in values]),expected)
        self.assertEqual(run(Detector(Config(sample_rate_hz=500)),[0]*100+[100]+[0]*4902),[])

    def test_dc_and_silence(self):
        for value in (-32768,0,2048,32767):
            self.assertEqual(run(AutoDetector(Config(sample_rate_hz=500)),[value]*5003),[])

    def test_reset_idle_and_causality(self):
        values=[0]*1100+[100]+[0]*600
        model=AutoDetector(Config(sample_rate_hz=500))
        for value in values[:700]:model.tick(value)
        previous=model.snapshot()
        for _ in range(10):model.tick(123,valid=False)
        self.assertEqual(previous.sample_index,model.sample_index)
        self.assertEqual(model.bootstrap_sum,0)
        model.tick(reset_n=False)
        first=run(model,values)
        self.assertEqual(first,run(AutoDetector(Config(sample_rate_hz=500)),values))
        longer=values+[32767,-32768]*200
        self.assertEqual(first,[e for e in run(AutoDetector(Config(sample_rate_hz=500)),longer) if e[0]<len(values)-30])

    def test_invalid_configuration(self):
        with self.assertRaises(ValueError):AutoDetector(seconds=0)
        with self.assertRaises(ValueError):AutoDetector(Config(energy_width=12))

    def test_bootstrap_fixed_point_bounds(self):
        for rate in (360,500):
            config=Config(sample_rate_hz=rate)
            windows=rate*2-config.window_length
            maximum=windows*config.window_length*65535
            self.assertLess(maximum,1<<32)
            reciprocal=(1<<32)//windows
            # 覆盖极值、整除边界和整个累加范围；近似不高估且最多差1码。
            values={0,1,maximum,maximum-1,windows-1,windows,windows+1}
            values.update(range(0,maximum+1,max(1,maximum//10000)))
            for value in values:
                exact=value//windows
                approximate=(value*reciprocal)>>32
                self.assertIn(exact-approximate,(0,1))

    def test_startup_pipeline_idle_commit_and_reset(self):
        model=AutoDetector(Config(sample_rate_hz=500))
        for i in range(1000):model.tick(100 if i==100 else 0)
        self.assertFalse(model.bootstrap_ready)
        self.assertEqual(model.bootstrap_phase,1)
        expected=max(1,(model.bootstrap_sum*((1<<32)//940))>>32)
        for phase in (2,3,0):
            model.tick(valid=False)
            self.assertEqual(model.bootstrap_phase,phase)
            self.assertEqual(model.sample_index,1000)
            self.assertFalse(model.qrs_valid)
        self.assertTrue(model.bootstrap_ready)
        self.assertEqual(model.noise_level,expected)
        model.tick(reset_n=False)
        self.assertFalse(model.bootstrap_ready)
        self.assertEqual(model.bootstrap_phase,0)


if __name__=='__main__':unittest.main()
