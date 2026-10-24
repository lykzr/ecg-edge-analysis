"""CH2标称换算及新500Hz双向中转；实际C核心/假串口，不代替无线实物。"""
from pathlib import Path
import csv,json,sys,time,unittest,uuid
from fractions import Fraction
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'sim'),str(ROOT/'src')]
from ecg_bridge_capture import NominalConverter
from ecg_capture_core import CaptureWorker,FIELDS
from ecg_bridge_worker import BridgeWorker
from ecg_bridge_protocol import encode
import test_pipeline500 as pipeline
from test_runtime_link import Node

class ConversionTests(unittest.TestCase):
 def test_exact_rational_boundaries_sign_channel_and_saturation(self):
  c=NominalConverter()
  for code in [-8388608,-166400,-20800,-3,-2,-1,0,1,2,3,20800,166400,8388607]:
   q=Fraction(code*2420*4096,6*8388607)
   m=(2*abs(q.numerator)+q.denominator)//(2*q.denominator)
   n=-m if q<0 else m
   self.assertEqual(c.convert((123,code)),max(-32768,min(32767,n)))
  self.assertGreater(c.clipped,0)
  self.assertEqual(c.convert((-8388608,0)),0)
  self.assertAlmostEqual(c.millivolts(8388607),2420/6)
  self.assertFalse(c.metadata()['calibrated'])
 def test_dc_constant_shift_invariance_and_fresh_session(self):
  a=NominalConverter(dc_block=True);b=NominalConverter(dc_block=True)
  x=[int(1000*((i%30)-15)) for i in range(2000)]
  self.assertEqual([a.convert((0,v)) for v in x],[b.convert((0,v+550000)) for v in x])
  c=NominalConverter(dc_block=True)
  self.assertEqual([c.convert((0,550000)) for _ in range(3000)],[0]*3000)
  self.assertEqual(NominalConverter(dc_block=True).convert((0,550000)),0)
 def test_dc_independent_recurrence_and_saturation(self):
  c=NominalConverter(dc_block=True);last=600000.;y=0.
  for code in [600000,610000,580000,600000,8388607,-8388608,600000]:
   y=500/(500+2*3.141592653589793*.5)*(y+code-last);last=code
   import math
   v=y*2420*4096/(6*8388607)
   expected=int(math.copysign(math.floor(abs(v)+.5),v))
   self.assertEqual(c.convert((0,code)),max(-32768,min(32767,expected)))
  self.assertGreater(c.clipped,0)
 def test_reject_wrong_types_and_double_offset(self):
  for pair in [(0,8388608),(0,-8388609),(0,1.),(0,True),(1,)]:
   with self.assertRaises(ValueError):NominalConverter().convert(pair)
 def test_rounding_is_symmetric_within_half_unit(self):
  c=NominalConverter()
  for code in range(0,160000,137):
   plus=c.convert((0,code));minus=c.convert((0,-code))
   self.assertEqual(plus,-minus)
   self.assertLessEqual(abs(plus-code*c.numerator/c.denominator),.5)

class Vendor500Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  pipeline.PipelineTests.setUpClass();cls.lib=pipeline.PipelineTests.lib
  cls.folder=pipeline.PipelineTests.folder/'vendor';cls.folder.mkdir()
 def convert_codes(self,codes):
  c=NominalConverter(dc_block=True);return [c.convert((0,x)) for x in codes]
 def output(self):return self.folder/uuid.uuid4().hex[:10]
 def source(self,count=1000):
  p=self.output().with_suffix('.csv')
  with p.open('w',newline='',encoding='utf-8') as f:
   w=csv.writer(f);w.writerow(FIELDS)
   for i in range(count):w.writerow([i/500,8388608,8388608+(20800 if i%400==50 else -520),999999,-999999])
  return p
 def test_vendor_csv_c_core_units_echo_saved_original(self):
  p=self.source();node=Node(self.lib);node.close=lambda:None
  worker=BridgeWorker('csv',p,'fake',self.output(),profile='runtime500',realtime=False,port_factory=lambda *a:node,pause=0)
  worker.start();worker.join(15)
  if worker.is_alive():worker.stop();worker.join(5)
  info,cap,_,(waves,events,header)=worker.snapshot()
  self.assertFalse(worker.is_alive());self.assertIsNone(info['error'],info);self.assertEqual(info['confirmed'],1000)
  self.assertEqual((header.source,header.fs,header.scale),('REPLAY',500,4096))
  self.assertEqual((worker.directory/'capture/source.csv').read_bytes(),p.read_bytes())
  self.assertIsNone(cap['shift']);self.assertEqual(cap['conversion']['pga_gain'],6)
  with (worker.directory/'capture/normalized.csv').open() as stream:saved=list(csv.DictReader(stream))
  self.assertEqual([int(r['sample']) for r in saved],self.convert_codes([20800 if i%400==50 else -520 for i in range(1000)]))
  self.assertEqual([row[2] for row in waves],[int(r['sample']) for r in saved])
 def test_adc_34byte_fragmented_uses_same_converter(self):
  codes=[0,20800,-20800,2]*100
  data=b'garbage'+b''.join(b'\xaa\xbb'+b''.join((8388608).to_bytes(4,'big')+(x+8388608).to_bytes(4,'big') for x in codes[i:i+4]) for i in range(0,len(codes),4))
  class Source:
   def __init__(self):self.data=data;self.closed=False
   def read(self,n):part=self.data[:71];self.data=self.data[71:];return part
   def close(self):self.closed=True
  source=Source();node=Node(self.lib);node.close=lambda:None
  w=BridgeWorker('serial','radio','zynq',self.output(),profile='runtime500',sample_limit=len(codes),source_factory=lambda *a:source,port_factory=lambda *a:node,pause=0)
  w.start();w.join(15)
  if w.is_alive():w.stop();w.join(5)
  info,cap,_,(waves,events,h)=w.snapshot();self.assertIsNone(info['error'],info);self.assertTrue(source.closed)
  self.assertEqual((info['confirmed'],h.source,h.scale),(400,'ADC',4096))
  self.assertEqual([x[2] for x in waves],self.convert_codes(codes))
  self.assertEqual(cap['initial_bytes_skipped'],7)
 def test_no_first_byte_times_out_and_preserves_record(self):
  t=[0.]
  def clock():t[0]+=.4;return t[0]
  class Silent:
   def read(self,n):return b''
   def close(self):pass
  w=CaptureWorker('serial','fake',self.output(),normalization='nominal500',serial_factory=lambda *a:Silent(),clock=clock)
  w.start();w.join(3);self.assertFalse(w.is_alive());self.assertIn('TimeoutError',w.snapshot()[0]['error'])
 def test_stop_and_new_worker_reset_dc_and_session(self):
  source=self.source(3000)
  node=Node(self.lib);node.close=lambda:None
  w=BridgeWorker('csv',source,'fake',self.output(),profile='runtime500',port_factory=lambda *a:node)
  w.start();deadline=time.monotonic()+3
  while w.capture.snapshot()[0]['total']<30 and w.is_alive() and time.monotonic()<deadline:time.sleep(.005)
  w.stop();w.join(5)
  info=w.snapshot()[0];self.assertIsNone(info['error'],info);self.assertEqual(info['reason'],'stopped_by_user')
  self.assertTrue(info['done']);self.assertEqual(info['confirmed'],w.capture.snapshot()[0]['total']);self.assertLess(info['confirmed'],3000)
  second=Node(self.lib);second.close=lambda:None
  fresh=BridgeWorker('csv',self.source(100),'fake',self.output(),profile='runtime500',port_factory=lambda *a:second,realtime=False)
  fresh.start();fresh.join(5);self.assertIsNone(fresh.snapshot()[0]['error'])
  with (fresh.directory/'capture/normalized.csv').open() as stream:self.assertEqual(next(csv.DictReader(stream))['sample'],'0')
 def test_adc_requires_scale4096(self):
  for scale,ok in [('4096',True),('-1',False)]:
   node=Node(self.lib)
   for b in encode('I,ECG-IN-1,adc,500,ADC,'+scale):self.lib.ecg_link_feed(node.state,b,node.now)
   for _ in range(100):node.tick()
   self.assertIn(b',READY,' if ok else b',ERROR,',bytes(node.rx))
 def test_cli_default_uses_integrated_vendor_path(self):
  import contextlib,io,ecg_bridge
  source=self.source(100);node=Node(self.lib);node.close=lambda:None;out=self.output()
  def factory(*args,**kwargs):return BridgeWorker(*args,**kwargs,port_factory=lambda *a:node,realtime=False)
  args=['ecg_bridge.py','--vendor-csv',str(source),'--rate','500','--source','REPLAY','--zynq-port','fake','--output-dir',str(out)]
  with patch.object(sys,'argv',args),patch('ecg_bridge_worker.BridgeWorker',side_effect=factory),contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(ecg_bridge.main(),0)
  saved=json.loads((out/'summary.json').read_text(encoding='utf-8'))
  self.assertEqual((saved['profile'],saved['confirmed']),('runtime500',100))
 def test_new_ui_routes_vendor_to_runtime500(self):
  import tkinter as tk
  from ui.bridge import BridgePanel
  root=tk.Tk();root.withdraw()
  try:
   dev=dict(port='COM1',label='fake',device_id='unit',candidate=True)
   with patch('ui.bridge.enumerate_ports',return_value=([dev],[])),patch('ui.bridge.remembered_identity',return_value=''),patch('ui.bridge.BridgeWorker') as Worker:
    p=BridgePanel(root);p.start('csv','vendor.csv')
    self.assertEqual(Worker.call_args.kwargs['profile'],'runtime500')
    self.assertIn('自动处理',p.shift_box.master.grid_slaves(row=2,column=0)[0].cget('text'))
    p.window.destroy()
  finally:root.destroy()

if __name__=='__main__':unittest.main()
