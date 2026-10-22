"""离线核对系统发布的完整文件、两套硬件、源码及精选实板字节证据；不连接板卡。"""
import argparse
import ast
import binascii
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe(base,name):
    if not isinstance(name,str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('发布路径须为正斜杠相对文件')
    p=PurePosixPath(name)
    if p.is_absolute() or PureWindowsPath(name).drive or '..' in p.parts:
        raise ValueError('发布路径越界')
    target=base.joinpath(*p.parts).resolve();target.relative_to(base.resolve())
    return target


def manifest(directory):
    data=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    for name,row in data['files'].items():
        path=safe(directory,name)
        if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:
            raise ValueError('文件或哈希不符: '+name)
    return data


def evidence(directory,case,count=None,reason=None):
    base=directory/'evidence/cases'/case
    summary=json.loads((base/'summary.json').read_text(encoding='utf-8'))
    if not summary['passed']:raise ValueError('原实板用例未通过')
    raw=(base/'usb_rx.log').read_bytes()
    if not raw.endswith(b'\n'):raise ValueError('接收尾行不完整')
    controls=[];wave=[];events=[];end=False
    for line in raw.splitlines():
        f=line.decode('ascii').split(',')
        if f[0]=='A':
            body,crc=line.rsplit(b'*',1)
            if binascii.crc32(body)!=int(crc,16):raise ValueError('确认CRC错误')
            controls.append(body.decode('ascii').split(','))
        elif f[0]=='W':
            seq,n=int(f[1]),int(f[2])
            if seq!=len(wave) or len(f)!=3+2*n:raise ValueError('波形序号/长度异常')
            for i in range(n):
                if f[4+2*i]!='NA':raise ValueError('未提供的滤波被填值')
                wave.append(int(f[3+2*i]))
        elif f[0]=='E':events.append(f)
        elif f[0]=='T':
            if f[4]!='NA' or f[6:9]!=['0','-1','0']:raise ValueError('状态报告异常/已知丢弃')
        elif line.startswith(b'L,I,END reason=completed '):end=True
        elif f[0] not in ('H','L'):raise ValueError('未知接收报文')
    if reason:
        assert not wave and not events and controls[-1][3:]==['0','ERROR',reason]
    else:
        assert count==len(wave)==summary['confirmed']==summary['echoed'] and end
        assert controls[-1][3:]==[str(count),'DONE','NA']
        assert all(v==((20000 if i//500%2==0 else -20000) if i%500==100 else 0) for i,v in enumerate(wave))
        assert len(events)==count//500
        for i,f in enumerate(events):
            assert list(map(int,f[1:4]))==[i+1,70+500*i,0 if i==0 else 500]
            assert f[5:]==['?','-1']
    return dict(samples=len(wave),events=len(events),reason=reason)


def check(directory,repository=None):
    directory=Path(directory).resolve()
    data=manifest(directory)
    assert data['version']=='20261021-system-jtag-v1'
    assert data['flash_programming']=='NOT_PERFORMED'
    actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    assert actual==set(data['files'])|{'manifest.json'},'存在未列明的交付文件'
    art=json.loads((directory/'artifacts.json').read_text(encoding='utf-8'))
    assert art['version']==data['version']
    assert not any(art['scope'][k] for k in ('wireless','manual_gui','ecg_accuracy','cnn_int8_pl','flash'))
    for name,row in art['sources'].items():
        assert digest(safe(directory,name))==row['sha256'],name
        if repository is not None:
            assert digest(safe(Path(repository),row['source']))==row['sha256'],row['source']
    bridge=manifest(directory/'bridge');smoke=manifest(directory/'smoke')
    for folder in ('smoke','bridge'):
        hardware=directory/folder/'hardware'
        with zipfile.ZipFile(hardware/'ecg_system_candidate.xsa') as z:
            assert z.read('ecg_system_candidate.bit')==(hardware/'ecg_system_candidate.bit').read_bytes()
        elf=directory/folder/'prebuilt'/('ecg_'+folder+'.elf')
        blob=elf.read_bytes()
        assert blob[:6]==b'\x7fELF\x01\x01' and int.from_bytes(blob[18:20],'little')==40
    assert digest(directory/'smoke/hardware/ecg_system_candidate.bit')!=digest(directory/'bridge/hardware/ecg_system_candidate.bit')
    assert bridge['elf_sha256']==art['bridge_build']['elf_sha256']==digest(directory/'bridge/prebuilt/ecg_bridge.elf')
    for name,h in art['smoke_core_unchanged'].items():assert digest(directory/'smoke'/name)==h
    for name,h in art['bridge_build']['source_sha256'].items():assert digest(directory/'src/ps/ecg_bridge'/name)==h
    for p in directory.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
    cases=dict(paced=evidence(directory,'paced_01',60003),recovery=evidence(directory,'paced_03',5003))
    for case,reason in [('bad-crc_02','BAD_CRC'),('partial_03','PARTIAL_TIMEOUT'),('idle_03','INPUT_TIMEOUT')]:
        cases[case]=evidence(directory,case,reason=reason)
    return dict(passed=True,version=data['version'],files=len(actual),cases=cases,
                source_match_checked=repository is not None,hardware_operated=False,
                scope='offline release/evidence checks, not new board or manual GUI validation')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'releases/latest')
    parser.add_argument('--repository',type=Path)
    args=parser.parse_args()
    print(json.dumps(check(args.directory,args.repository),ensure_ascii=False))
