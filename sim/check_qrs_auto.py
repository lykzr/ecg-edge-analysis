"""启动学习修复：受控/用户CSV逐周期XSim核对和公开标注开发回归，不连接板卡。"""
import argparse
import csv
from dataclasses import asdict
import json
import os
from pathlib import Path
import random
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/reference'),str(ROOT/'data')]
from ecg_auto import AutoDetector
from ecg_reference import Config,Detector
from ecg_dataset import load_record,metrics,BEAT_CODES


def events(model,values):
    result=[]
    for value in values:
        s=model.feed_sample(value) if isinstance(model,AutoDetector) else model.tick(value)
        if s.qrs_valid:result.append(s.qrs_sample_index)
    return result


def simulate(name,values,rate,base,bin_dir,reset_at=()):
    out=base/name;out.mkdir()
    rng=random.Random(718)
    frames=[(0,0,0)]*3
    for index,value in enumerate(values):
        if index in reset_at:
            frames.append((0,0,0))
        frames.append((1,1,value))
        frames.extend([(1,0,value)]*rng.randrange(3))
    (out/'vectors.txt').write_text(''.join(f'{r} {v} {s}\n' for r,v,s in frames),encoding='ascii')
    tb=(ROOT/'sim/tb_ecg_reference.sv').read_text(encoding='utf-8').replace('ecg_qrs_detector #(','ecg_qrs_auto #(')
    (out/'driver.sv').write_text(tb,encoding='utf-8')
    (out/'top.sv').write_text(f'module tb_reference; ecg_reference_driver #(.SAMPLE_RATE_HZ({rate})) driver(); endmodule\n',encoding='ascii')
    commands=[['xvlog','-sv',ROOT/'src/rtl/ecg_qrs_auto.sv',out/'driver.sv',out/'top.sv'],
              ['xelab','tb_reference','-s','auto_snapshot','-mt','off'],['xsim','auto_snapshot','-runall']]
    for args in commands:
        args=[bin_dir/(args[0]+'.bat'),*args[1:]]
        temporary=out/'temp';temporary.mkdir(exist_ok=True)
        environment=dict(os.environ,TEMP=str(temporary),TMP=str(temporary))
        done=subprocess.run(list(map(str,args)),cwd=out,capture_output=True,text=True,env=environment)
        (out/(Path(args[0]).stem+'.log')).write_text(done.stdout+done.stderr,encoding='utf-8')
        if done.returncode:raise RuntimeError(str(args[0])+' failed')
    log=(out/'xsim.log').read_text(encoding='utf-8')
    if 'PASS REFERENCE_TRACE' not in log or 'Fatal:' in log:raise ValueError('仿真未完整通过')
    model=AutoDetector(Config(sample_rate_hz=rate));ev=[]
    with (out/'rtl_trace.csv').open(newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==len(frames)
    for i,(row,(reset,valid,value)) in enumerate(zip(rows,frames)):
        state=asdict(model.tick(value,bool(valid),bool(reset)))
        for key,expected in state.items():
            if int(row[key])!=expected:raise AssertionError((name,i,key,int(row[key]),expected))
        if state['qrs_valid']:ev.append(state['qrs_sample_index'])
    return dict(cycles=len(frames),samples=len(values),events=ev,reference_state_fields=15,reference_fields_equal=True)


def simulate_axi(base,bin_dir):
    """保留既有AXI/FIFO断言，仅增加候选需要的启动及峰确认输入。"""
    out=base/'axi';out.mkdir()
    wrapper=(ROOT/'src/rtl/ecg_qrs_axi_lite.sv').read_text(encoding='utf-8')
    assert wrapper.count('ecg_qrs_detector #(')==1
    (out/'wrapper.sv').write_text(wrapper.replace('ecg_qrs_detector #(','ecg_qrs_auto #('),encoding='utf-8')
    tb=(ROOT/'sim/tb_axi_lite.sv').read_text(encoding='utf-8')
    anchor="  write_sample(16'sd20000);read_reg(4,status);read_reg(8,index1);"
    assert tb.count(anchor)==1
    tb=tb.replace(anchor,"  for(i=0;i<1000;i=i+1)write_sample(0);\n  write_sample(16'sd20000);for(i=0;i<61;i=i+1)write_sample(0);read_reg(4,status);read_reg(8,index1);")
    anchor="  write_sample(16'sd20000);read_reg(4,status);read_reg(8,index2);"
    assert tb.count(anchor)==1
    tb=tb.replace(anchor,"  write_sample(16'sd20000);for(i=0;i<61;i=i+1)write_sample(0);read_reg(4,status);read_reg(8,index2);")
    (out/'driver.sv').write_text(tb.replace('#200000;','#2000000;'),encoding='utf-8')
    commands=[['xvlog','-sv',ROOT/'src/rtl/ecg_qrs_auto.sv',out/'wrapper.sv',out/'driver.sv'],
              ['xelab','tb_axi_lite','-s','axi_auto_snapshot','-mt','off'],['xsim','axi_auto_snapshot','-runall']]
    temporary=out/'temp';temporary.mkdir()
    for args in commands:
        done=subprocess.run([str(bin_dir/(args[0]+'.bat')),*map(str,args[1:])],cwd=out,capture_output=True,text=True,
                            env=dict(os.environ,TEMP=str(temporary),TMP=str(temporary)))
        (out/(args[0]+'.log')).write_text(done.stdout+done.stderr,encoding='utf-8')
        if done.returncode:raise RuntimeError('AXI '+args[0]+' failed')
    log=(out/'xsim.log').read_text(encoding='utf-8')
    if 'PASS AXI split channels' not in log or 'Fatal:' in log:raise ValueError('AXI断言未通过')
    return dict(passed=True,scope='actual candidate detector and AXI RTL; startup/peak-confirm inputs added, original bus/FIFO assertions retained')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--vivado-bin',type=Path,required=True)
    parser.add_argument('--raw',type=Path,required=True)
    parser.add_argument('--csv-input',type=Path,default=ROOT/'tmp/system_rounds_20261020/input_analysis_01/raw_shift8.csv')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    low=[0]*3503
    for i in range(100,3503,500):low[i]=100 if (i//500)%2==0 else -100
    cfg=Config(sample_rate_hz=500)
    expected=events(AutoDetector(cfg),low)
    assert expected and all(i>=970 for i in expected)
    assert events(Detector(cfg),low)==[]
    assert events(AutoDetector(cfg),[2048]*3503)==[]
    with args.csv_input.open(newline='') as source:
        values=[int(r['sample']) for r in csv.DictReader(source)]
    result=dict(scope='development reproduction; no independent held-out accuracy or hardware claim',software={},rtl={})
    for name,xs in [('low_pulses',low),('constant',[2048]*3503),('user_csv',values)]:
        result['software'][name]=dict(original=events(Detector(cfg),xs),candidate=events(AutoDetector(cfg),xs))
        result['rtl'][name]=simulate(name,xs,500,out,args.vivado_bin.resolve())
        assert result['rtl'][name]['events']==result['software'][name]['candidate']
    prefix,_,_=load_record(args.raw,'100','MLII')
    result['rtl']['record100_prefix']=simulate('record100_prefix',prefix[:3000],360,out,args.vivado_bin.resolve())
    reset_values=[0]*4503
    for i in range(100,4503,500):reset_values[i]=100 if i//500%2==0 else -100
    result['rtl']['reset_learning']=simulate('reset_learning',reset_values,500,out,args.vivado_bin.resolve(),reset_at=(700,2500))
    result['rtl_axi']=simulate_axi(out,args.vivado_bin.resolve())
    for record in ('100','101','103'):
        samples,labels,info=load_record(args.raw,record,'MLII')
        reference=[i for i,c in labels if c in BEAT_CODES]
        result['software'][record]=dict(source=info,all_samples=len(samples),warmup_samples=720,
            original=metrics(reference,events(Detector(),samples),54)[0],
            candidate=metrics(reference,events(AutoDetector(),samples),54)[0])
        # 启动两秒保留在全段计分中，不删掉为提高数字；另外报告预热后的定位。
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
