"""固定种子INT8小向量对真实XSim；不加载模型/数据集，不修改板级工程。"""
import argparse,hashlib,json,os,random,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/reference'))
from ecg_int8_ops import conv1d_valid,maxpool1d,requantize

def run(output,bin_dir,gcc_version):
    output=Path(output).resolve();output.relative_to(ROOT/'tmp');output.mkdir(parents=True,exist_ok=False)
    rng=random.Random(2401);configs=[(s,r) for s in (0,1,7,31) for r in (0,1)]
    tb=['module tb; logic clk=0; always #5 clk=~clk; logic reset=1,start=0;',
        'logic signed [7:0] x[0:17],w[0:11]; logic signed [31:0] bias[0:1];',
        'wire signed [7:0] pool[0:8]; ecg_int8_maxpool #(.LENGTH(18),.WIDTH(2)) p(x,pool);',
        'wire signed [7:0] tailpool[0:3]; ecg_int8_maxpool #(.LENGTH(18),.WIDTH(4)) pt(x,tailpool);']
    for n,(shift,relu) in enumerate(configs):
        tb += [f'wire busy{n},done{n}; wire signed [7:0] y{n}[0:13];',
               f'ecg_int8_conv #(.CIN(2),.COUT(2),.LENGTH(9),.KERNEL(3),.SHIFT({shift}),.RELU({relu})) d{n}(clk,reset,start,x,w,bias,busy{n},done{n},y{n});']
    tb+=['initial begin','repeat(2) @(negedge clk); reset=0;']
    vectors=[]
    for case in range(24):
        xs=[[rng.randint(-128,127) for _ in range(9)] for _ in range(2)]
        ws=[[[rng.randint(-128,127) for _ in range(3)] for _ in range(2)] for _ in range(2)]
        bs=[rng.randint(-10000,10000) for _ in range(2)]
        if case==0:xs=[[-128]*9,[127]*9];ws=[[[-128]*3,[-128]*3],[[127]*3,[127]*3]];bs=[0,0]
        if case==1:xs=[[0]*9,[0]*9];bs=[1,-1]
        if case==2:xs=[[-128]*9,[-128]*9];ws=[[[-128]*3,[-128]*3],[[127]*3,[127]*3]];bs=[2147385343,-2147385343]
        vectors.append(dict(x=xs,w=ws,bias=bs))
        for i,v in enumerate(sum(xs,[])):tb.append(f'x[{i}]={v};')
        for i,v in enumerate([v for filt in ws for row in filt for v in row]):tb.append(f'w[{i}]={v};')
        for i,v in enumerate(bs):tb.append(f'bias[{i}]={v};')
        for i,v in enumerate(maxpool1d([sum(xs,[])],2)[0]):tb.append(f'#1; if($signed(pool[{i}]) !== {v}) $fatal(1,"pool case{case} {i}");')
        for i,v in enumerate(maxpool1d([sum(xs,[])],4)[0]):tb.append(f'#1; if($signed(tailpool[{i}]) !== {v}) $fatal(1,"pool tail case{case} {i}");')
        tb+=['@(negedge clk);start=1; @(negedge clk);start=0;', 'repeat(20) @(negedge clk);start=1; @(negedge clk);start=0;repeat(20) @(negedge clk);']
        # 14 outputs * 6 products =84 cycles. Assert completion on the last cycle.
        tb+=['repeat(43) @(negedge clk);']
        for n,(shift,relu) in enumerate(configs):
            tb.append(f'if(busy{n} !== 0 || done{n} !== 1) $fatal(1,"completion case{case} cfg{n}");')
            ys=sum(conv1d_valid(xs,ws,bs,shift,relu),[])
            for i,v in enumerate(ys):tb.append(f'if($signed(y{n}[{i}]) !== {v}) $fatal(1,"conv case{case} cfg{n} index{i}");')
        tb+=['@(negedge clk);']
    tb+=['start=1; @(negedge clk);start=0; repeat(3) @(negedge clk);reset=1; @(negedge clk);reset=0;']
    for n in range(8):tb.append(f'if(busy{n} !== 0 || done{n} !== 0) $fatal(1,"reset");')
    tb+=['$display("PASS INT8_OPS vectors=24 configs=8 outputs=2688 pool=312 reset=8");$finish;end',
         'initial begin #1000000; $fatal(1,"watchdog");end endmodule']
    (output/'tb.sv').write_text('\n'.join(tb),encoding='utf-8')
    (output/'vectors.json').write_text(json.dumps(vectors),encoding='utf-8')
    commands=[['xvlog.bat','-sv',str(ROOT/'src/rtl/ecg_int8_ops.sv'),str(output/'tb.sv')],
              ['xelab.bat','tb','-s','ops_snapshot','-mt','off','-gcc_version',gcc_version],['xsim.bat','ops_snapshot','-runall']]
    for i,cmd in enumerate(commands):
        cmd[0]=str(Path(bin_dir)/cmd[0]);result=subprocess.run(cmd,cwd=output,capture_output=True,timeout=180,
            env=dict(os.environ,TMP=str(output),TEMP=str(output)))
        (output/f'step_{i}.log').write_bytes(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(f'{cmd[0]} failed; see {output}')
    if b'PASS INT8_OPS' not in (output/'step_2.log').read_bytes():raise AssertionError('未见仿真通过标记')
    # 明确半值、负值和饱和的独立手算检查。
    assert [requantize(v,1) for v in (1,-1,3,-3,1000,-1000)]==[1,-1,2,-2,127,-128]
    try:conv1d_valid([[1]],[[[1]]],[2147483647],0)
    except ValueError:pass
    else:raise AssertionError('必须拒绝最坏溢出配置')
    summary=dict(passed=True,vectors=24,configs=8,convolution_outputs=2688,pool_outputs=312,reset_cases=8,
                 source_sha256=hashlib.sha256((ROOT/'src/rtl/ecg_int8_ops.sv').read_bytes()).hexdigest(),
                 scope='actual XSim integer operators only; no final CNN/accuracy/board claim')
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--vivado-bin',required=True)
    p.add_argument('--gcc-version',default='auto',choices=['auto','gcc-6.2.0','gcc-8.3.0','gcc-9.3.0'])
    a=p.parse_args();run(a.output,a.vivado_bin,a.gcc_version)
