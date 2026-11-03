"""读取固定证据入口；未实现/未板测不返回猜测的占用或性能。"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def resources():
    evidence=ROOT/'docs/evidence/cnn_int8_fast_20261103/resources.json'
    if not evidence.is_file():evidence=ROOT/'docs/evidence/cnn_fast_20261103/resources.json'
    if not evidence.is_file():evidence=ROOT/'docs/evidence/cnn_int8_20261103/resources.json'
    if evidence.is_file():
        result=json.loads(evidence.read_text(encoding='utf-8'))
        if result.get('device')!='xc7z020clg400-2' or result.get('stage')!='routed':raise ValueError('资源证据身份不符')
        return result
    return dict(device='xc7z020clg400-2',stage='pending',board_verified=False,
        capacity=dict(lut=53200,ff=106400,bram36=140,dsp=220),rows=[],
        note='INT8候选尚无通过时序检查的布局布线资源证据。资源表不使用HLS估算替代实现结果。')
