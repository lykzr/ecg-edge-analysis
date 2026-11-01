"""显式授权下验证网页后台与实板双协议；使用独立目录，不操作Flash或采集端。"""
from pathlib import Path
import argparse,csv,hashlib,io,json,sys,time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/pc'),str(ROOT/'src')]
from ecg_ports import enumerate_ports
from ecg_web_service import LiveManager
from verify_hgb_uart import verify

def run(port,device_id,output):
    output=Path(output).resolve();output.relative_to(ROOT/'tmp')
    ports,_=enumerate_ports()
    if len([p for p in ports if p['port']==port and p['device_id']==device_id])!=1:
        raise ValueError('USB身份不匹配；不打开串口')
    output.mkdir(parents=True,exist_ok=False)
    manager=LiveManager(output/'live')
    source=np.loadtxt(ROOT/'model/inference/examples/synthetic500.csv',delimiter=',')[:5000]
    quantized=np.clip(np.copysign(np.floor(abs(source*4096)+.5),source),-32768,32767).astype(int)
    stream=io.StringIO();writer=csv.writer(stream);writer.writerow(['index','sample','fs','scale'])
    writer.writerows((i,int(x),500,4096) for i,x in enumerate(quantized))
    standard=stream.getvalue().encode()
    config=dict(zynq_port=port,zynq_port_identity=device_id,realtime=False,standard_preprocess='hp05')
    checks=[]
    try:
        # 模型→原实时QRS→模型，不复位，证明两个入口可在同一固件复用。
        for number,board_model in enumerate((True,False,True)):
            if number==2:
                text=io.StringIO();w=csv.writer(text)
                w.writerow(['timestamp(s)','resp_raw','ecg_raw','resp_filtered','ecg_filtered'])
                adc=np.rint(source*(6*8388607)/2420).astype(int)+8388608
                w.writerows((f'{i/500:.3f}',8388608,int(x),0,0) for i,x in enumerate(adc))
                payload=text.getvalue().encode();kind='bridge_csv'
            else:payload=standard;kind='standard500'
            upload=manager.upload('hardware-check','controlled.csv',payload)
            identifier=manager.start('hardware-check',dict(config,kind=kind,board_model=board_model,upload_id=upload['id']))['id']
            deadline=time.monotonic()+100
            while time.monotonic()<deadline:
                snapshot=manager.snapshot('hardware-check',identifier)
                if not snapshot['active']:break
                time.sleep(.05)
            else:
                manager.stop('hardware-check',identifier)
                raise TimeoutError('实板后台未在100秒结束')
            (output/f'snapshot_{number}.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            assert not snapshot['info']['error'],snapshot['info']
            assert snapshot['info']['reason']=='completed',snapshot['info']
            assert snapshot['info']['source_samples']==5000 and snapshot['info']['confirmed']==5000
            directory=manager.jobs[identifier]['directory']
            if board_model:
                comparison=verify(directory,directory/'input_mv.csv')
                assert snapshot['result']['waveform_origin']=='host_input'
                assert snapshot['info']['execution_location']=='zynq_arm'
            else:
                assert snapshot['info']['echoed']==5000 and snapshot['info']['done']
                comparison=dict(passed=True,echoed=5000,events=len(snapshot['result']['events']))
            svg=manager.svg('hardware-check',identifier)
            assert '<svg' in svg and '<polyline' in svg
            (output/f'plot_{number}.svg').write_text(svg,encoding='utf-8')
            assert manager.file('hardware-check',identifier,'summary.json').is_file()
            try:manager.snapshot('other-owner',identifier)
            except LookupError:pass
            else:raise AssertionError('所有者隔离失效')
            checks.append(dict(kind=kind,board_model=board_model,id=identifier,comparison=comparison,
                files={p.relative_to(directory).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in directory.rglob('*') if p.is_file()}))
    finally:manager.shutdown()
    result=dict(passed=True,physical_arm_uart=True,port=port,device_id=device_id,checks=checks,
        no_reset_between_sessions=True,flash_written=False,
        scope='网页后台实板标准CSV及厂商格式受控回放；非浏览器人工验收、真实无线或连续模型分类')
    (output/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('port','device-id','output'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();run(args.port,args.device_id,args.output)
