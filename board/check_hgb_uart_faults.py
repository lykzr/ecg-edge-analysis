"""显式端口身份下检查独立HGB应用拒绝与恢复；会向板卡发送受控故障。"""
from pathlib import Path
import argparse
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/pc'))
from ecg_hgb import Channel, READY, LEGACY_READY, transfer
from ecg_bridge_serial import DuplexSerial
from ecg_ports import enumerate_ports


def run(port, device_id, output):
    ports, _ = enumerate_ports()
    assert len([p for p in ports if p['port'] == port and p['device_id'] == device_id]) == 1
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    serial = DuplexSerial(port)
    checks = []
    try:
        channel = Channel(serial, output)
        try:
            channel.expect(LEGACY_READY)
            channel.write(b'I,HGB-BATCH-1,100,360,mV,hp05,1000\n')
            channel.expect('F,0,BAD_HEADER'); checks.append('reject_360Hz')
            channel.expect(LEGACY_READY)
            channel.write(b'I,HGB-BATCH-1,101,500,mV,hp05,1000\n')
            channel.expect('A,101,READY,32')
            channel.write(b'B,101,0,1,00000000\n'+bytes(8))
            channel.expect('F,101,BAD_CRC'); checks.append('reject_crc')
            channel.expect(LEGACY_READY)
            channel.write(b'I,HGB-BATCH-1,102,500,mV,raw,1000\n')
            channel.expect('A,102,READY,32'); channel.write(b'X,102\n')
            channel.expect('S,102,CANCEL'); checks.append('cancel')
            channel.expect(LEGACY_READY)
            channel.write(b'I,HGB-BATCH-1,103,500,mV,raw,1000\n')
            channel.expect('A,103,READY,32')
            channel.expect('F,103,INPUT_TIMEOUT_OR_UART'); checks.append('idle_timeout')
            # 将READY留给后面的新会话读取，不重启板卡。
        finally:
            channel.close()
        recovery = output/'recovery'
        recovery.mkdir()
        result = transfer(np.zeros(1000), serial, recovery, 'raw', sid=104)
        assert result['passed'] and not result['events'] and result['clipped'] == 0
        checks.append('new_session_after_faults_no_reset')
        receipt = dict(passed=True, checks=checks, port=port, device_id=device_id,
                       hardware_operated=True, flash_written=False,
                       scope='controlled complete bad CRC/cancel/idle timeout; not physical unplug or arbitrary byte resynchronization')
        (output/'verification.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(receipt))
    finally:
        serial.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', required=True); p.add_argument('--device-id', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args(); run(a.port, a.device_id, a.output)
