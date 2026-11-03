"""FP32全连接输出分四ROM bank，不改权重、精度或单输出累加顺序。"""
import argparse
import json
from pathlib import Path
from export_cnn_hls import run
from model.cnn_fourclass.network import load_model


def export(output):
    output = Path(output)
    run(output)
    state = load_model(0).state_dict()
    text = ''
    for layer in ('rr.0', 'head.0', 'head.3'):
        w, b = state[layer + '.weight'].numpy(), state[layer + '.bias'].numpy()
        weights = [w[lane::4].reshape(-1).tolist() for lane in range(4)]
        biases = [b[lane::4].tolist() for lane in range(4)]
        def array(name, data):
            return f'static const float {name}[4][{len(data[0])}]={{' + ',\n'.join('{' + ','.join(format(v, '.9e') + 'f' for v in row) + '}' for row in data) + '};\n'
        name = {'rr.0': 'rr', 'head.0': 'head', 'head.3': 'out'}[layer]
        text += array('dense_' + name + '_weights', weights) + array('dense_' + name + '_bias', biases)
    (output / 'cnn_dense_fast_weights.h').write_text(text, encoding='utf-8')
    print(json.dumps(dict(precision='FP32', dense_output_lanes=4, retrained=False, order='same per-output accumulation')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    export(parser.parse_args().output)
