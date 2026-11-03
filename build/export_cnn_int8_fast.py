"""INT8全连接头按输出分四bank；沿用原量化参数与黄金向量，不训练。"""
import argparse
import hashlib
import json
from pathlib import Path

from export_cnn_int8 import export
from model.cnn_fourclass.network import load_model
from model.cnn_fourclass.int8_reference import Int8Reference


def run(output):
    output = Path(output).resolve()
    export(output)
    state = {k: v.numpy() for k, v in load_model(0).state_dict().items()}
    reference = Int8Reference(state)
    weights, scales = reference.weights['head.0.weight']
    arrays = [
        ('q_head_weights_fast', 'int8_t', [weights[lane::4].reshape(-1).tolist() for lane in range(4)]),
        ('q_head_scales_fast', 'float', [scales[lane::4].reshape(-1).tolist() for lane in range(4)]),
        ('q_head_bias_fast', 'float', [state['head.0.bias'][lane::4].tolist() for lane in range(4)]),
    ]
    text = '// 冻结INT8 head.0，四路输出独立ROM；单输出累加及FP32缩放顺序不变。\n'
    for name, kind, banks in arrays:
        def values(row):
            return ','.join(str(int(v)) if kind == 'int8_t' else format(float(v), '.9e') + 'f' for v in row)
        text += f'static const {kind} {name}[4][{len(banks[0])}]={{' + ',\n'.join('{' + values(row) + '}' for row in banks) + '};\n'
    header = output / 'cnn_int8_fast_weights.h'
    header.write_text(text, encoding='utf-8')
    convnames = ['wave.0.weight'] + [f'wave.{b}.body.{c}.weight' for b in (3, 4, 5) for c in (0, 3)]
    convbanks = [[] for _ in range(16)]
    for name in convnames:
        w, _ = reference.weights[name]
        for lane in range(16):
            convbanks[lane].extend(w[lane].reshape(-1).tolist())
    convtext = 'static const int8_t q_conv16_weights[16][494]={' + ',\n'.join(
        '{' + ','.join(str(int(v)) for v in bank) + '}' for bank in convbanks) + '};\n'
    convheader = output / 'cnn_int8_conv16_weights.h'
    convheader.write_text(convtext, encoding='utf-8')
    info = dict(change='four dense output banks; optional sixteen convolution output banks', training=False, weights_changed=False,
                scale_rounding_saturation_changed=False, storage='LUTRAM ROM requested',
                original_header_sha256=hashlib.sha256((output / 'cnn_int8_weights.h').read_bytes()).hexdigest(),
                fast_header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(),
                conv16_header_sha256=hashlib.sha256(convheader.read_bytes()).hexdigest())
    (output / 'fast_export.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(info))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
