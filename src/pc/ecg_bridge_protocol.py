"""仅ECG-IN-1输入及A确认；不解析厂商帧或ECG-UART-1结果。"""
import binascii
import re


def encode(body):
    data = body.encode('ascii')
    if any(c < 32 or c > 126 or c == 42 for c in data):
        raise ValueError('正文不能含控制字符或星号')
    line = data + f'*{binascii.crc32(data):08X}\n'.encode('ascii')
    if len(line) > 256:
        raise ValueError('输入行超长')
    return line


def decode(line):
    if len(line) > 256 or not line.endswith(b'\n'):
        raise ValueError('输入行超长或不完整')
    if not re.fullmatch(rb'[\x20-\x29\x2B-\x7E]+\*[0-9A-F]{8}\n', line):
        raise ValueError('输入行格式错误')
    body, crc = line[:-1].rsplit(b'*', 1)
    if binascii.crc32(body) != int(crc, 16):
        raise ValueError('CRC错误')
    fields = body.decode('ascii').split(',')
    if any(not f for f in fields):
        raise ValueError('字段为空')
    return fields


def ack(line):
    fields = decode(line)
    if len(fields) != 6 or fields[:2] != ['A', 'ECG-IN-1']:
        raise ValueError('不是ECG-IN-1确认')
    _, _, session, next_value, state, reason = fields
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', session):
        raise ValueError('会话错误')
    if not re.fullmatch(r'0|[1-9][0-9]*', next_value) or int(next_value) > 1800000:
        raise ValueError('确认序号错误')
    if state not in ('READY', 'ACCEPTED', 'DONE', 'ERROR') or not re.fullmatch(r'[A-Z_]+', reason):
        raise ValueError('确认状态错误')
    if state != 'ERROR' and reason != 'NA':
        raise ValueError('正常确认携带错误')
    return session, int(next_value), state, reason


def samples(seq0, values):
    values = tuple(values)
    if not isinstance(seq0, int) or not 0 <= seq0 <= 1800000 or not 1 <= len(values) <= 32:
        raise ValueError('输入批次范围错误')
    if seq0 + len(values) > 1800000 or any(type(x) is not int or not -32768 <= x <= 32767 for x in values):
        raise ValueError('样本越界')
    return encode(','.join(['D', str(seq0), str(len(values)), *map(str, values)]))
