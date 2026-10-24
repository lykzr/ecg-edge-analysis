"""故障文案及隐藏Tk状态；不代替人工界面或物理断连。"""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'src')]
from ui.status import bridge_status
from ecg_monitor_core import Monitor,demo_frames
class StateTests(unittest.TestCase):
 def test_failure_never_complete(self):
  text,error,history=bridge_status(dict(error='保存失败',reason='completed'),False)
  self.assertTrue(error and history);self.assertNotIn('完整运行结束',text)
 def test_quiet_and_recovery(self):
  info=dict(error=None,state='running',reason=None,sample_age_s=2.1)
  self.assertIn('不等于断连',bridge_status(info,True)[0]);self.assertTrue(bridge_status(info,True)[2])
  info['sample_age_s']=0;self.assertFalse(bridge_status(info,True)[2])
 def test_stop_and_unknown_reason(self):
  self.assertIn('手动',bridge_status(dict(reason='stopped_by_user'),False)[0])
  self.assertTrue(bridge_status(dict(reason=None),False)[1])
 def test_monitor_stale_cards_and_new_wave(self):
  import tkinter as tk
  from ui.monitor import Application
  m=Monitor()
  for _,data in demo_frames(3.01):m.feed(data)
  root=tk.Tk();root.withdraw()
  try:
   with patch('ui.monitor.enumerate_ports',return_value=([],[])):
    app=Application(root,m);app.running=True;app.kind='serial';app._sample_count_seen=0
    with patch('ui.monitor.time.monotonic',return_value=100):app._update_cards()
    with patch('ui.monitor.time.monotonic',return_value=103):app._update_cards()
    self.assertIn('历史数值',app.card_notes['hr'].get());self.assertEqual(app.card_vars['cls'].get(),'未提供')
    m.feed(f'W,{m.expected_wave},1,0,NA\n'.encode())
    with patch('ui.monitor.time.monotonic',return_value=104):app._update_cards()
    self.assertNotIn('历史数值',app.card_notes['hr'].get())
  finally:root.destroy()
 def test_panel_error_and_stale_event(self):
  import tkinter as tk
  from ui.bridge import BridgePanel
  root=tk.Tk();root.withdraw()
  info=dict(state='finished',reason='failed',error='写盘失败',sample_rate_hz=360,profile='runtime360',source='REPLAY',source_status='已关闭',result_status='已关闭',source_samples=2,confirmed=2,echoed=2,sample_age_s=3)
  cap=dict(total=2,clipped=0)
  event=SimpleNamespace(seq=1,pos=0,rr=0,hr=None)
  try:
   with patch('ui.bridge.enumerate_ports',return_value=([],[])),patch('ui.bridge.remembered_identity',return_value=None):
    panel=BridgePanel(root);panel.window.withdraw()
    panel.worker=SimpleNamespace(is_alive=lambda:False,snapshot=lambda:(info,cap,(),((),[event],None)))
    panel.tick();self.assertIn('出错',panel.state.get());self.assertEqual(str(panel.state_label.cget('foreground')),'#b3261e')
    self.assertIn('历史数值',panel.events_text.get());self.assertIn('心率 未知',panel.events_text.get())
    panel.window.destroy()
  finally:root.destroy()
if __name__=='__main__':unittest.main()
