"""当前MIT-BIH解码、读取和计分公共函数；由历史实现原函数迁出，不改计算规则。"""
import csv
import hashlib
import re
import statistics
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/reference'))
from ecg_input import map_adc
BEAT_CODES=set(range(1,14)) | {25,30,34,35,38,41}

def decode212(data):
    if len(data) % 3:
        raise ValueError('212 数据长度不是三字节的整数倍')
    channels = [[], []]
    for a, b, c in zip(data[::3], data[1::3], data[2::3]):
        for channel, value in enumerate((a | ((b & 15) << 8), c | ((b >> 4) << 8))):
            channels[channel].append(value - 4096 if value & 2048 else value)
    return channels


def annotations(data):
    result, position, time = [], 0, 0
    while position < len(data):
        word = int.from_bytes(data[position:position+2], 'little')
        position += 2
        code, interval = word >> 10, word & 1023
        if not word:
            break
        if code == 59:
            high = int.from_bytes(data[position:position+2], 'little')
            low = int.from_bytes(data[position+2:position+4], 'little')
            delta = (high << 16) | low
            time += delta - (1 << 32) if delta & (1 << 31) else delta
            position += 4
        elif code == 63:
            position += interval + interval % 2
        elif code not in (60, 61, 62):
            time += interval
            result.append((time, code))
        if position > len(data):
            raise ValueError('标注文件被截断')
    return result


def match_beats(reference, detected, tolerance):
    # 有序一对一、固定容差匹配；不作事后整体平移，也不重复使用一个心搏。
    pairs, missed, extra = [], [], []
    i = j = 0
    while i < len(reference) and j < len(detected):
        delta = detected[j] - reference[i]
        if delta < -tolerance:
            extra.append(detected[j]); j += 1
        elif delta > tolerance:
            missed.append(reference[i]); i += 1
        else:
            pairs.append((i, j, delta)); i += 1; j += 1
    return pairs, missed + reference[i:], extra + detected[j:]


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f); writer.writerow(fields); writer.writerows(rows)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_record(raw, record, lead):
    official = {line.split()[1].lstrip('*'):line.split()[0]
                for line in (raw/'SHA256SUMS.txt').read_text().splitlines()}
    hashes = {f'{record}.{ext}':digest(raw/f'{record}.{ext}') for ext in ('hea','dat','atr')}
    if any(official.get(name) != value for name,value in hashes.items()):
        raise ValueError(f'{record} 官方SHA256不匹配')
    lines = (raw/f'{record}.hea').read_text().splitlines()
    header = lines[0].split()
    if header[:3] != [record,'2','360']:
        raise ValueError('仅支持360Hz双通道212记录')
    count = int(header[3])
    channels = decode212((raw/f'{record}.dat').read_bytes())
    selected = None
    for channel,line in zip(channels,lines[1:3]):
        fields = line.split()
        checksum = (sum(channel)+32768)%65536-32768
        if (fields[0] != record+'.dat' or fields[1] != '212' or
            len(channel) != count or channel[0] != int(fields[5]) or checksum != int(fields[6])):
            raise ValueError(f'{record} 解码首值/样本数/校验和错误')
        # 支持明确baseline或采用adc_zero；只接受已定义的mV单位。
        match = re.fullmatch(r'(\d+)(?:\((-?\d+)\))?(?:/mV)?',fields[2])
        if not match:
            raise ValueError('不支持的增益/单位字段')
        if fields[-1] == lead:
            if selected is not None:
                raise ValueError('导联名称不唯一')
            selected = (channel,int(match[2]) if match[2] is not None else int(fields[4]),int(match[1]))
    if selected is None:
        raise ValueError(f'{record} 缺少{lead}，停止而非自动换导联')
    payload = (raw/f'{record}.atr').read_bytes()
    if len(payload)%2 or payload[-2:] != b'\0\0':
        raise ValueError('标注缺少完整EOF')
    labels = annotations(payload)
    positions = [i for i,_ in labels]
    if positions != sorted(positions) or any(i<0 or i>=count for i in positions):
        raise ValueError('标注位置超界或不单调')
    samples,clipped = map_adc(*selected)
    return samples,labels,dict(source_sha256=hashes,input_clipped=clipped,
                              baseline=selected[1],adc_per_mv=selected[2],samples=count)


def metrics(reference, detected, tolerance):
    pairs, missed, extra = match_beats(reference,detected,tolerance)
    tp,fn,fp = len(pairs),len(missed),len(extra)
    errors = [delta*1000/360 for _,_,delta in pairs]
    rr_errors = [((detected[d]-detected[b])-(reference[c]-reference[a]))*1000/360
                 for (a,b,_),(c,d,_) in zip(pairs,pairs[1:]) if c==a+1 and d==b+1]
    return dict(TP=tp,FN=fn,FP=fp,sensitivity=tp/(tp+fn) if tp+fn else None,
                positive_predictivity=tp/(tp+fp) if tp+fp else None,
                F1=2*tp/(2*tp+fn+fp) if 2*tp+fn+fp else None,
                position_mae_ms=statistics.mean(map(abs,errors)) if errors else None,
                rr_mae_ms=statistics.mean(map(abs,rr_errors)) if rr_errors else None,
                matched_rr_intervals=len(rr_errors)),pairs,missed,extra


def aggregate(rows):
    tp,fn,fp = (sum(r[k] for r in rows) for k in ('TP','FN','FP'))
    count = sum(r['matched_rr_intervals'] for r in rows)
    return dict(TP=tp,FN=fn,FP=fp,sensitivity=tp/(tp+fn) if tp+fn else None,
        positive_predictivity=tp/(tp+fp) if tp+fp else None,F1=2*tp/(2*tp+fn+fp) if 2*tp+fn+fp else None,
        position_mae_ms=sum(r['position_mae_ms']*r['TP'] for r in rows if r['TP'])/tp if tp else None,
        rr_mae_ms=sum(r['rr_mae_ms']*r['matched_rr_intervals'] for r in rows if r['matched_rr_intervals'])/count if count else None,
        records=len(rows),records_passing=sum(r['provisional_gate']=='PASS' for r in rows))
