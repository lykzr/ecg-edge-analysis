"""Windows串口只读枚举；USB身份用于候选提示，不打开端口或发送探测命令。"""
import os
import re
import json
from pathlib import Path

from ecg_paths import ROOT

PORT_MEMORY = ROOT / 'tmp/pc_devices.json'


def select_port(ports, previous=None, *, identity='', excluded=''):
    """按USB实例跟随COM变化；记住的设备缺席时不退选另一个设备。"""
    available = [p for p in ports if p['port'].upper() != excluded.upper()]
    target = (previous or {}).get('device_id') or identity
    if target:
        matches = [p for p in available if p.get('device_id') == target]
        return matches[0]['port'] if len(matches) == 1 else ''
    return candidate_port(available)


def remembered_identity(role, path=PORT_MEMORY):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return data.get(role, '') if isinstance(data.get(role), str) else ''
    except (OSError, ValueError, AttributeError):
        return ''


def remember_identity(role, device, path=PORT_MEMORY):
    """仅由已识别的结果会话调用；保存USB身份，不把COM号当身份。"""
    if not device.get('device_id'):
        return
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict): data = {}
    except (OSError, ValueError):
        data = {}
    data[role] = device['device_id']
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.new')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def validate_port(port, previous, current, *, excluded=''):
    match = next((p for p in current if p['port'] == port), None)
    if port.upper() == excluded.upper() or match is None:
        raise ValueError('端口不可用或与另一连接冲突，请刷新后选择')
    if previous and previous.get('device_id') and previous['device_id'] != match.get('device_id'):
        raise ValueError('USB身份已变化，请刷新后重新选择，不能沿用旧COM号')
    return dict(match)


def candidate_port(ports, excluded=''):
    candidates = [p['port'] for p in ports if p.get('candidate') and p['port'].upper() != excluded.upper()]
    return candidates[0] if len(candidates) == 1 else ''


def enumerate_ports():
    if os.name != 'nt':
        return [], ['当前自动枚举仅支持Windows']
    import winreg as reg
    ports, warnings = {}, []
    try:
        with reg.OpenKey(reg.HKEY_LOCAL_MACHINE, r'HARDWARE\DEVICEMAP\SERIALCOMM') as key:
            for i in range(reg.QueryInfoKey(key)[1]):
                _, port, _ = reg.EnumValue(key, i)
                if re.fullmatch(r'COM[1-9][0-9]*', str(port), re.I):
                    ports[port.upper()] = dict(port=port.upper(), label='串口（身份未知）',
                                               device_id='', candidate=False)
    except FileNotFoundError:
        return [], ['未发现活动串口']
    except OSError as exc:
        return [], ['串口枚举失败：' + str(exc)]
    try:
        with reg.OpenKey(reg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Enum\USB') as usb:
            for i in range(reg.QueryInfoKey(usb)[0]):
                device = reg.EnumKey(usb, i)
                try:
                    with reg.OpenKey(usb, device) as dev:
                        for j in range(reg.QueryInfoKey(dev)[0]):
                            instance = reg.EnumKey(dev, j)
                            with reg.OpenKey(dev, instance) as node:
                                try:
                                    with reg.OpenKey(node, 'Device Parameters') as params:
                                        port = str(reg.QueryValueEx(params, 'PortName')[0]).upper()
                                except FileNotFoundError:
                                    continue
                                if port not in ports:
                                    continue
                                try:
                                    label = str(reg.QueryValueEx(node, 'FriendlyName')[0])
                                except FileNotFoundError:
                                    label = device
                                identity = device + '\\' + instance
                                hint = (device + ' ' + label).upper()
                                likely = any(s in hint for s in ('CH340', 'CH341', 'VID_1A86&PID_7523', 'VID_1A86&PID_5523'))
                                ports[port].update(label=label, device_id=identity, candidate=likely)
                except OSError as exc:
                    warnings.append('部分USB身份不可读：' + str(exc))
    except OSError as exc:
        warnings.append('USB身份枚举失败：' + str(exc))
    return sorted(ports.values(), key=lambda p: int(p['port'][3:])), warnings
