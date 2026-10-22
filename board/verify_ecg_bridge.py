"""已由用户JTAG启动后的有限实板数字验证；显式身份，不自动复位或写Flash。"""
import argparse
import csv
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/pc'))
from ecg_ports import enumerate_ports, validate_port
from ecg_bridge_core import BridgeClient
from ecg_bridge_records import BridgeRecords
from ecg_bridge_serial import DuplexSerial
from ecg_bridge_protocol import encode, ack


def pulse(index):
    return (20000 if (index//500)%2 == 0 else -20000) if index%500 == 100 else 0


def verify(port_name, device_id, output, mode, count):
    ports, warnings = enumerate_ports()
    identity = validate_port(port_name,dict(device_id=device_id),ports)
    if output.exists():
        raise FileExistsError('输出存在，不覆盖现场')
    # 限额、时长、门槛在打开串口前冻结并保存。
    plan = dict(mode=mode, samples=count, source='SYNTH', sample_rate_hz=500,
                paced_source_hz=500 if mode=='paced' else None,
                positive_gate='all confirmed/echoed/value/sequence/END/DONE; zero known drops; exact event index/RR',
                fault_gate='CRC-protected ERROR with expected reason, next=0; no W/E; no auto recovery',
                duration_limit_s=count/500+15 if mode=='paced' else 10,
                maximum_record_bytes=64*1024*1024, identity=identity, warnings=warnings,
                scope='USB_UART digital verification; no physical ADC timing, wireless, GUI or accuracy claim')
    records = BridgeRecords(output)
    (output/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    port = None
    summary = dict(reason='failed', error=None, plan=plan, passed=False)
    started = time.monotonic()
    try:
        port = DuplexSerial(port_name)
        client = BridgeClient(port,records.monitor,uuid.uuid4().hex,'SYNTH',write_log=records.write)
        origin = None; produced = 0
        injected = False
        while time.monotonic()-started < plan['duration_limit_s']:
            if mode=='paced':
                if client.started and client.waiting is None and origin is None:
                    origin = time.monotonic()
                if origin is not None and not client.eof:
                    due = min(count,int((time.monotonic()-origin)*500)+1)
                    batch = [pulse(i) for i in range(produced,due)]
                    for i,value in enumerate(batch,produced):
                        records.row('normalized.csv',[i,value])
                    client.add(batch); produced=due
                    if produced==count:
                        client.finish_source()
                client.pump()
                if client.done:
                    summary.update(client.summary(), reason='completed', passed=True)
                    break
            else:
                if not injected:
                    client.pump()
                    if client.started and client.waiting is None:
                        line = encode('D,0,1,20000')
                        if mode=='bad-crc':
                            line = line[:-2]+(b'0' if line[-2:-1]!=b'0' else b'1')+b'\n'
                        elif mode=='partial':
                            line = line[:5]
                        else:
                            line=b''
                        while line:
                            n=port.write(line)
                            if not n: raise TimeoutError('故障注入写入停滞')
                            records.write('upload.log',line[:n]);line=line[n:]
                        injected=True; fault_start=time.monotonic(); buffer=bytearray()
                else:
                    data=port.read(4096)
                    if data:
                        records.write('usb_rx.log',data);buffer.extend(data)
                        if len(buffer)>8192: raise ValueError('故障回应超长')
                        while b'\n' in buffer:
                            end=buffer.index(10)+1;line=bytes(buffer[:end]);del buffer[:end]
                            if line.startswith(b'A,'):
                                session,next_value,state,reason=ack(line)
                                expected={'bad-crc':'BAD_CRC','partial':'PARTIAL_TIMEOUT','idle':'INPUT_TIMEOUT'}[mode]
                                if (session,next_value,state,reason)!=(client.session,0,'ERROR',expected):
                                    raise ValueError('故障回应不符合冻结门槛')
                                records.write('controls.log',line)
                                summary.update(reason='expected_fault',passed=True,error_reason=reason,
                                               response_s=time.monotonic()-fault_start,
                                               accepted_samples=0)
                            elif line.startswith((b'W,',b'E,')):
                                raise ValueError('拒绝输入却出现波形/事件')
                            else:
                                records.monitor.feed(line)
                        if summary['passed']:
                            # 保存后续字节，确保没有延后冒出的波形/事件。
                            until=time.monotonic()+.2
                            while time.monotonic()<until:
                                extra=port.read(4096)
                                if extra:
                                    records.write('usb_rx.log',extra);buffer.extend(extra)
                                time.sleep(.001)
                            if buffer:
                                raise ValueError('错误结束后仍有未核对回应')
                            break
            time.sleep(.001)
        if not summary['passed']:
            raise TimeoutError('冻结时长内未达到验收条件')
        if mode=='paced':
            expected=[70+500*i for i in range(count//500)]
            summary['expected_event_positions']=expected
            summary['expected_events']=len(expected)
            summary['produced']=produced
    except (Exception,KeyboardInterrupt) as exc:
        summary.update(reason='failed',passed=False,error=f'{type(exc).__name__}: {exc}')
    finally:
        if port: port.close()
        summary['wall_seconds']=time.monotonic()-started
        summary['hardware_operated']=True
        records.close(summary)
    if summary['passed'] and mode=='paced':
        with (output/'results/events.csv').open(encoding='utf-8-sig',newline='') as f:
            events=list(csv.DictReader(f))
        with (output/'results/samples.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
        summary['monitor']=json.loads((output/'results/summary.json').read_text(encoding='utf-8'))
        # 按实际CSV列名做逐值复核；不只比较总数。
        gates = dict(
            counts_equal=len(rows)==count==summary['confirmed']==summary['echoed'],
            values_equal=all(int(r['seq'])==i and int(r['index'])==i and int(r['raw'])==pulse(i)
                             and r['filt']=='' and r['source']=='SYNTH' for i,r in enumerate(rows)),
            events_equal=len(events)==len(expected) and all(
                int(r['evt'])==i+1 and int(r['rpos'])==expected[i] and int(r['rr'])==(0 if i==0 else 500)
                and r['cls']=='?' for i,r in enumerate(events)),
            no_known_gaps=all(summary['monitor']['counts'].get(k,0)==0 for k in ('wave_gap','event_gap')),
            no_parse_errors=summary['monitor']['protocol_counts'].get('invalid',0)==0,
            drained=summary['pending_bytes']==0 and summary['incomplete_rx_bytes']==0 and summary['done'])
        summary['gates']=gates
        if not all(gates.values()):
            summary.update(reason='failed',passed=False,error='关闭后逐值/事件/完整性复核未通过')
        summary['events_recorded']=len(events)
        (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True)
    parser.add_argument('--device-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('paced','bad-crc','partial','idle'),required=True)
    parser.add_argument('--samples',type=int,default=60003)
    args=parser.parse_args()
    if not 503<=args.samples<=120003 or args.samples%500!=3:
        parser.error('样本数503..120003且模500余3，冻结完整脉冲期及末批')
    result=verify(args.port,args.device_id,args.output,args.mode,args.samples)
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)
