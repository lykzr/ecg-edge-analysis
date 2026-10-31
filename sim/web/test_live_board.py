"""网页适配到现有PS C核心：两路假串口，不操作实物。"""
import ctypes as ct
from collections import deque
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from ecg_web_service import LiveManager
from ecg_bridge_worker import BridgeWorker
from ecg_runtime_worker import RuntimeWorker

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT/'sim'))


@pytest.fixture(scope='module')
def library():
    import uuid
    spec=importlib.util.spec_from_file_location('web_rate500_generator',PROJECT/'build/generate_rate500_runtime.py')
    generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)
    folder=PROJECT/'tmp/web_c_tests'/uuid.uuid4().hex
    generator.run(folder)
    compiler=os.environ.get('ECG_HOST_CC') or shutil.which('gcc')
    if not compiler: raise RuntimeError('实际C核验需要已有GCC；不自动安装或跳过')
    library=folder/('web_link.dll' if os.name=='nt' else 'web_link.so')
    sources=[PROJECT/'src/ps/ecg_rate500'/name for name in ('pipeline500.c','rate500.c')]
    sources += [folder/'runtime500_bridge.c',folder/'link500.c',PROJECT/'src/ps/ecg_classification/classification.c',PROJECT/'sim/ecg_runtime_link_host.c']
    command=[compiler,'-shared','-std=c11','-O2','-ffp-contract=off']+([] if os.name=='nt' else ['-fPIC'])
    command += ['-I'+str(PROJECT/'src/ps'/name) for name in ('ecg_classification','ecg_runtime','ecg_rate500')]+[str(path) for path in sources]+['-lm','-o',str(library)]
    process=subprocess.run(command,capture_output=True,timeout=60,env=dict(os.environ,TMP=str(folder),TEMP=str(folder)))
    (folder/'compile.log').write_bytes(process.stdout+process.stderr)
    assert process.returncode==0,process.stderr.decode(errors='replace')
    lib=ct.CDLL(str(library))
    lib.ecg_link_size.restype=ct.c_size_t;lib.ecg_pipeline_size.restype=ct.c_size_t
    lib.ecg_link_init.argtypes=[ct.c_void_p,Io,ct.c_void_p,ct.c_uint]
    lib.ecg_link_feed.argtypes=[ct.c_void_p,ct.c_ubyte,ct.c_uint64]
    lib.ecg_link_step.argtypes=[ct.c_void_p,ct.c_uint64]
    return lib


READY=ct.CFUNCTYPE(ct.c_int,ct.c_void_p)
BYTE=ct.CFUNCTYPE(None,ct.c_void_p,ct.c_ubyte)
class Io(ct.Structure):
    _fields_=[('ctx',ct.c_void_p),('ready',READY),('byte',BYTE)]


class Node:
    """沿用sim/test_runtime_link.py的碎片串口宿主，仅绑定所需C接口。"""
    def __init__(self,lib):
        self.lib=lib;self.now=0;self.rx=deque()
        self.state=ct.create_string_buffer(lib.ecg_link_size())
        self.pipeline=ct.create_string_buffer(lib.ecg_pipeline_size())
        self.callbacks=(READY(lambda _:1),BYTE(lambda _,x:self.rx.append(x)))
        self.io=Io(None,*self.callbacks)
        lib.ecg_link_init(self.state,self.io,self.pipeline,0)
    def read(self,size):
        self.now+=100;self.lib.ecg_link_step(self.state,self.now)
        return bytes(self.rx.popleft() for _ in range(min(size,len(self.rx))))
    def write(self,data):
        data=data[:7]
        for byte in data:self.lib.ecg_link_feed(self.state,byte,self.now)
        return len(data)


@pytest.mark.parametrize('kind',['bridge_csv','standard500','bridge_serial'])
def test_real_c_echo_through_manager(tmp_path, monkeypatch, library, kind):
    from ecg_bridge_capture import NominalConverter
    monkeypatch.setattr('ecg_web_service.remember_identity',lambda *args,**kwargs:None)
    devices = [dict(port='COM9',device_id='board',candidate=True),dict(port='COM4',device_id='capture',candidate=False)]
    node = Node(library)
    node.closed = False
    node.close = lambda: setattr(node,'closed',True)
    codes = [20000 if i%400==50 else -200 for i in range(1000)]
    payload = b''.join(b'\xaa\xbb'+b''.join((8388608).to_bytes(4,'big')+(x+8388608).to_bytes(4,'big') for x in codes[i:i+4]) for i in range(0,len(codes),4))
    class Source:
        def __init__(self): self.data=payload; self.closed=False
        def read(self,size): part,self.data=self.data[:71],self.data[71:]; return part
        def close(self): self.closed=True
    source = Source()
    def factory(kind,path,directory,config):
        options = dict(port_factory=lambda *args:node,realtime=False,clock=lambda:node.now/1e6)
        if kind == 'standard500':
            return RuntimeWorker(path,'COM9',directory,sampling_hz=500,**options)
        return BridgeWorker('serial' if kind=='bridge_serial' else 'csv','COM4' if kind=='bridge_serial' else path,
                            'COM9',directory,source_factory=lambda *args:source,sample_limit=1000 if kind=='bridge_serial' else None,
                            pause=0,profile='runtime500',**options)
    manager = LiveManager(tmp_path/'manager',port_enumerator=lambda:(devices,[]),worker_factory=factory)
    config = dict(kind=kind,zynq_port='COM9',zynq_port_identity='board',capture_port='COM4',capture_port_identity='capture')
    if kind == 'standard500':
        content = ('index,sample,fs,scale\n'+'\n'.join(f'{i},{code},500,4096' for i,code in enumerate(codes))).encode()
    else:
        content = ('timestamp(s),resp_raw,ecg_raw,resp_filtered,ecg_filtered\n'+'\n'.join(f'{i/500:.3f},8388608,{8388608+code},0,0' for i,code in enumerate(codes))).encode()
    if kind != 'bridge_serial': config['upload_id']=manager.upload('owner','input.csv',content)['id']
    identifier = manager.start('owner',config)['id']
    try:
        worker=manager.jobs[identifier]['worker']; worker.join(20)
        if worker.is_alive(): worker.stop(); worker.join(5)
        snapshot=manager.snapshot('owner',identifier)
        assert not snapshot['active'], snapshot['info']
        assert snapshot['info']['error'] is None, snapshot['info']
        assert snapshot['info']['confirmed']==1000
        assert snapshot['info']['echoed']==1000
        assert snapshot['result']['header']['fs']==500
        assert node.closed
        if kind=='bridge_serial': assert source.closed
        if kind=='standard500': expected=codes
        else:
            converter=NominalConverter(dc_block=True)
            expected=[converter.convert((0,code)) for code in codes]
        assert [row['raw'] for row in snapshot['result']['samples']]==expected
        assert len(snapshot['source_samples'])==1000
        assert snapshot['result']['cls']=='未提供'
        if kind!='bridge_serial':
            input_file='input.csv' if kind=='standard500' else 'capture/source.csv'
            assert manager.file('owner',identifier,input_file).read_bytes()==content
    finally:
        manager.shutdown()
