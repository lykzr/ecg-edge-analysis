"""实际PS C候选的主机核验；不仿称板上QRS/CNN。"""
import ctypes as ct
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/reference'))
from ecg_classifier import normalize_rr
from test_classifier import spec

class Req(ct.Structure):
    _fields_=[(n,ct.c_uint32) for n in ('generation','beat_id','position','rr_samples','sampling_hz','ready_at','input_status')]+[('waveform',ct.c_float*128),('rr',ct.c_float*3)]
class Res(ct.Structure):
    _fields_=[('request',Req),('status',ct.c_uint32),('valid',ct.c_uint32),('class_id',ct.c_int32)]

class PsClassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc=os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
        if not cc:raise RuntimeError('需要已有GCC，不自动安装或跳过C核验')
        cls.folder=ROOT/'tmp/classification_20261023/ps_tests'/uuid.uuid4().hex[:10]
        cls.folder.mkdir(parents=True,exist_ok=False)
        lib=cls.folder/('class.dll' if os.name=='nt' else 'class.so')
        command=[cc,'-shared','-std=c11','-O2','-Wall','-Wextra','-Werror']
        if os.name!='nt':command+=['-fPIC']
        command += [str(ROOT/'src/ps/ecg_classification/classification.c'),str(ROOT/'sim/ecg_class_host.c'),'-o',str(lib)]
        p=subprocess.run(command,capture_output=True,env=dict(os.environ,TMP=str(cls.folder),TEMP=str(cls.folder)),timeout=60)
        (cls.folder/'compile.log').write_bytes(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
        cls.lib=ct.CDLL(str(lib))
        for n in ('state','request','result'):
            getattr(cls.lib,'ecg_class_'+n+'_size').restype=ct.c_size_t
        L=cls.lib
        L.ecg_class_init.argtypes=[ct.c_void_p,ct.c_uint32,ct.POINTER(ct.c_uint8),ct.c_uint64]
        L.ecg_class_submit.argtypes=[ct.c_void_p,ct.POINTER(Req),ct.c_uint64]
        for n,t in [('take',Req),('expire',Res),('cancel',Res)]:
            getattr(L,'ecg_class_'+n).argtypes=[ct.c_void_p,ct.POINTER(t),ct.c_uint64]
        L.ecg_class_complete.argtypes=[ct.c_void_p,ct.c_uint32,ct.c_uint32,ct.c_uint32,ct.c_int32,ct.POINTER(Res),ct.c_uint64]
        L.ecg_class_normalize_rr.argtypes=[ct.POINTER(ct.c_float)]*4

    def setUp(self):
        self.state=ct.create_string_buffer(self.lib.ecg_class_state_size())
        self.assertEqual(self.lib.ecg_class_init(self.state,1,(ct.c_uint8*32)(),10),0)

    def req(self,n=1,status=0):
        r=Req();r.generation=1;r.beat_id=n;r.position=n*360;r.rr_samples=360
        r.sampling_hz=360;r.ready_at=r.position+240;r.input_status=status
        return r

    def test_layout_and_rr_float32_agreement(self):
        self.assertEqual(ct.sizeof(Req),self.lib.ecg_class_request_size())
        self.assertEqual(ct.sizeof(Res),self.lib.ecg_class_result_size())
        s=spec()
        for values in ([.25,.25,.25],[0.,1.,.125]):
            out=(ct.c_float*3)()
            self.assertEqual(self.lib.ecg_class_normalize_rr((ct.c_float*3)(*values),(ct.c_float*3)(*s.rr_mean),(ct.c_float*3)(*s.rr_std),out),0)
            np.testing.assert_allclose(list(out),normalize_rr(values,s),rtol=1e-6,atol=1e-6)

    def test_busy_order_and_completion_metadata(self):
        for n in range(1,5):self.assertEqual(self.lib.ecg_class_submit(self.state,ct.byref(self.req(n)),0),0)
        self.assertEqual(self.lib.ecg_class_submit(self.state,ct.byref(self.req(5)),0),1)
        out=Req();self.assertEqual(self.lib.ecg_class_take(self.state,ct.byref(out),1),1)
        result=Res()
        self.assertEqual(self.lib.ecg_class_complete(self.state,1,1,0,2,ct.byref(result),2),1)
        self.assertEqual((result.class_id,result.valid,result.request.position),(2,1,360))
        self.assertEqual(self.lib.ecg_class_submit(self.state,ct.byref(self.req(5)),3),0)

    def test_timeout_late_result_and_reset(self):
        self.lib.ecg_class_submit(self.state,ct.byref(self.req()),0)
        r=Req();self.lib.ecg_class_take(self.state,ct.byref(r),0)
        out=Res();self.assertEqual(self.lib.ecg_class_expire(self.state,ct.byref(out),10),1)
        self.assertEqual((out.status,out.valid,out.class_id),(5,0,-1))
        self.assertEqual(self.lib.ecg_class_complete(self.state,1,1,0,0,ct.byref(out),11),-1)
        self.lib.ecg_class_init(self.state,2,(ct.c_uint8*32)(),10)
        self.assertEqual(self.lib.ecg_class_submit(self.state,ct.byref(self.req(2)),12),-1)

    def test_pending_timeout_cancel_and_clock(self):
        for n in (1,2):self.lib.ecg_class_submit(self.state,ct.byref(self.req(n)),0)
        r=Req();out=Res()
        self.assertEqual(self.lib.ecg_class_take(self.state,ct.byref(r),10),0)
        self.assertEqual(self.lib.ecg_class_expire(self.state,ct.byref(out),10),1)
        self.assertEqual(self.lib.ecg_class_cancel(self.state,ct.byref(out),11),1)
        self.assertEqual((out.status,out.request.beat_id),(7,2))
        self.assertEqual(self.lib.ecg_class_cancel(self.state,ct.byref(out),12),0)
        self.assertEqual(self.lib.ecg_class_take(self.state,ct.byref(r),9),-1)

    def test_invalid_input_no_success_and_bad_class(self):
        r=self.req(status=2);r.rr_samples=0
        self.assertEqual(self.lib.ecg_class_submit(self.state,ct.byref(r),0),0)
        w=Req();out=Res();self.lib.ecg_class_take(self.state,ct.byref(w),0)
        self.assertEqual(self.lib.ecg_class_complete(self.state,1,1,0,0,ct.byref(out),1),-1)
        self.assertEqual(self.lib.ecg_class_complete(self.state,1,1,2,-1,ct.byref(out),2),1)
        self.assertFalse(out.valid)

    def test_nonfinite_duplicate_and_normalization_unchanged_on_error(self):
        r=self.req();r.waveform[5]=float('nan')
        self.assertEqual(self.lib.ecg_class_submit(self.state,ct.byref(r),0),-1)
        self.assertEqual(self.lib.ecg_class_submit(self.state,ct.byref(self.req()),0),0)
        self.assertEqual(self.lib.ecg_class_submit(self.state,ct.byref(self.req()),0),-1)
        out=(ct.c_float*3)(7,7,7)
        self.assertEqual(self.lib.ecg_class_normalize_rr((ct.c_float*3)(1,2,3),(ct.c_float*3)(),(ct.c_float*3)(0,1,1),out),-1)
        self.assertEqual(list(out),[7,7,7])

if __name__=='__main__':unittest.main()
