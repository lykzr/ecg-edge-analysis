"""分类接口/队列/旧PC协议检查；假后端不声称分类能力，不训练。"""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/reference'),str(ROOT/'src/pc')]
from ecg_classifier import ModelSpec, Request, Result, ClassQueue, prepare, normalize_rr, event_line, digest
from ecg_beat_window import BeatWindow
from ecg_monitor_core import Monitor


def spec(kind='none'):
    return ModelSpec('unit-model','0'*64,digest(ROOT/'model/protocols/cnn_git_v1_protocol.json'),
                     '1'*64,(.2,.2,.25),(.1,.1,.02),False,kind)


def request(i=1,status='OK'):
    s=spec()
    return Request('session',i,360*i,0 if status=='MISSING_RR' else 360,360,360*i+240,
                   s.model_id,s.weights_sha256,s.preprocess_sha256,(0.,)*128,(0.,)*3,status)


class ClassifierTests(unittest.TestCase):
    def test_prepare_complete_rr_and_first_unknown(self):
        s=spec()
        b=BeatWindow(200,500,360,360,128,tuple(int(1000*np.sin(i*.1)) for i in range(320)),(360,))
        r=prepare(b,'session',1,s)
        self.assertEqual(len(r.waveform),128)
        np.testing.assert_array_equal(r.rr,normalize_rr([.25,.25,.25],s))
        first=prepare(replace(b,rr_samples=0,rr_history=()),'session',1,s)
        self.assertEqual(first.status,'MISSING_RR')
        self.assertEqual(first.rr,())

    def test_training_fold_normalization_and_clip(self):
        x=normalize_rr([0.,1.,.25],spec())
        np.testing.assert_allclose(x,[-2.,5.,0.],atol=1e-6)
        with self.assertRaises(ValueError):normalize_rr([float('nan'),1,1],spec())
        with self.assertRaises(ValueError):replace(spec(),rr_std=(0.,1.,1.))

    def test_hash_unit_shape_and_numeric_rejected(self):
        b=BeatWindow(200,500,360,360,128,tuple(range(320)),(360,))
        with self.assertRaises(ValueError):prepare(b,'session',1,replace(spec(),preprocess_sha256='0'*64))
        with self.assertRaises(ValueError):prepare(replace(b,units_per_mv=1),'session',1,spec())
        for changes in [dict(waveform=(0.,)*127),dict(rr=(float('inf'),0.,0.)),dict(rr=(6.,0.,0.)),dict(beat_id=0)]:
            with self.assertRaises(ValueError):replace(request(),**changes)

    def test_order_busy_not_accepted_and_backpressure(self):
        q=ClassQueue(spec(),capacity=1);q.reset('session')
        self.assertEqual(q.submit(request(),0),'ACCEPTED')
        self.assertEqual(q.submit(request(2),1),'BUSY')
        r=q.take(1)
        self.assertEqual(q.complete(Result(r,'NO_MODEL'),2).status,'NO_MODEL')
        self.assertEqual(q.submit(request(2),3),'ACCEPTED')
        with self.assertRaises(ValueError):q.submit(request(),4)

    def test_timeout_and_late_completion(self):
        q=ClassQueue(spec(),timeout_ms=10);q.reset('session')
        q.submit(request(),0);r=q.take(0)
        self.assertEqual(q.expire(10).status,'TIMEOUT')
        with self.assertRaises(ValueError):q.complete(Result(r,'NO_MODEL'),11)
        self.assertEqual(q.submit(request(2),12),'ACCEPTED')

    def test_waiting_deadline_and_clock_reverse(self):
        q=ClassQueue(spec(),timeout_ms=10);q.reset('session')
        q.submit(request(),0)
        self.assertIsNone(q.take(10))
        self.assertEqual(q.expire(10).status,'TIMEOUT')
        with self.assertRaises(ValueError):q.take(9)

    def test_cancel_and_reset_reject_previous_session(self):
        q=ClassQueue(spec());q.reset('session')
        q.submit(request(),0);r=q.take(0);q.submit(request(2),0)
        self.assertEqual([x.status for x in q.cancel(1)],['CANCELLED','CANCELLED'])
        q.reset('next')
        with self.assertRaises(ValueError):q.submit(request(3),2)
        with self.assertRaises(ValueError):q.complete(Result(r,'NO_MODEL'),3)

    def test_invalid_request_cannot_become_known(self):
        q=ClassQueue(spec());q.reset('session')
        q.submit(request(status='MISSING_RR'),0);r=q.take(0)
        with self.assertRaises(ValueError):q.complete(Result(r,'OK',0,True),1)
        self.assertFalse(q.complete(Result(r,'MISSING_RR'),2).valid)

    def test_wrong_model_rejected(self):
        q=ClassQueue(spec());q.reset('session')
        with self.assertRaises(ValueError):q.submit(replace(request(),weights_sha256='2'*64),0)
        with self.assertRaises(ValueError):event_line(Result(request(),'NO_MODEL'),replace(spec(),model_id='different'))

    def test_single_event_wire_and_duplicate_rejected(self):
        m=Monitor()
        m.feed(b'H,ECG-UART-1,unit,session,SYNTH,TEST-ONLY,360,4096,0x1D\n')
        line=event_line(Result(request(),'OK',2,True),spec('development'))
        m.feed(line)
        self.assertEqual(m.events[-1].cls,'V')
        self.assertIsNone(m.events[-1].conf)
        m.feed(line)
        self.assertEqual(m.counts['events'],1)
        self.assertTrue(m.decoder.counts['invalid'])

    def test_fake_backend_suppressed_and_unknown_fields(self):
        m=Monitor();m.feed(b'H,ECG-UART-1,unit,session,SYNTH,TEST-ONLY,360,4096,0xD\n')
        m.feed(event_line(Result(request(),'OK',0,True),spec('fake')))
        self.assertEqual(m.events[-1].cls,'?')
        self.assertFalse(m.decoder.counts['invalid'])

    def test_fault_results_through_unchanged_monitor(self):
        m=Monitor();m.feed(b'H,ECG-UART-1,unit,session,REPLAY,CLASS-FAULT,360,4096,0x15\n')
        q=ClassQueue(spec('development'),capacity=1,timeout_ms=10);q.reset('session')
        q.submit(request(),0);active=q.take(0)
        self.assertEqual(q.submit(request(2),0),'BUSY')
        timeout=q.expire(10);m.feed(event_line(timeout,q.spec))
        with self.assertRaises(ValueError):q.complete(Result(active,'OK',0,True),11)
        q.submit(request(2),11);q.take(11)
        m.feed(event_line(q.complete(Result(request(2),'BACKEND_ERROR'),12),q.spec))
        q.submit(request(3),13)
        for r in q.cancel(14):m.feed(event_line(r,q.spec))
        q.reset('new-session')
        with self.assertRaises(ValueError):q.submit(request(4),15)
        self.assertEqual(m.counts['events'],3)
        self.assertEqual([e.cls for e in m.events],['?','?','?'])
        self.assertEqual(m.counts['event_gap'],0)
        self.assertEqual(m.decoder.counts['invalid'],0)

    def test_result_and_spec_status_consistency(self):
        with self.assertRaises(ValueError):Result(request(),'TIMEOUT',0,True)
        with self.assertRaises(ValueError):replace(spec(),accepted=True)
        with self.assertRaises(ValueError):replace(spec(),rr_std=(float('nan'),1,1))


if __name__=='__main__':unittest.main()
