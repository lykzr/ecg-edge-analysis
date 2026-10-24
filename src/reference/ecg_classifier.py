"""ECG-CLASS-1候选：完整输入适配、有界调度及一次性E结果；不训练。"""
from collections import deque
from dataclasses import dataclass, asdict, replace
import hashlib
import json
import math
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[2]
CLASSES = ('N', 'S', 'V', 'F')
TOKEN = re.compile(r'^[A-Za-z0-9_.-]{1,32}$')
SHA = re.compile(r'^[0-9a-f]{64}$')
STATES = {'OK', 'NO_MODEL', 'MISSING_RR', 'INVALID_INPUT', 'WINDOW_INCOMPLETE',
          'TIMEOUT', 'BACKEND_ERROR', 'CANCELLED'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    weights_sha256: str
    preprocess_sha256: str
    normalization_sha256: str
    rr_mean: tuple
    rr_std: tuple
    accepted: bool = False
    kind: str = 'none'

    def __post_init__(self):
        if not TOKEN.fullmatch(self.model_id) or self.kind not in ('none', 'fake', 'development', 'accepted'):
            raise ValueError('模型身份/后端类型无效')
        if any(not SHA.fullmatch(x) for x in (self.weights_sha256, self.preprocess_sha256, self.normalization_sha256)):
            raise ValueError('需要完整SHA256')
        if len(self.rr_mean) != 3 or len(self.rr_std) != 3:
            raise ValueError('RR归一化必须三维')
        if not all(math.isfinite(x) for x in (*self.rr_mean, *self.rr_std)) or min(self.rr_std) < struct.unpack('f', struct.pack('f', .01))[0]:
            raise ValueError('归一化参数非有限或std低于训练下限')
        if self.accepted != (self.kind == 'accepted'):
            raise ValueError('已接受标志与后端身份矛盾')

    @classmethod
    def from_dict(cls, data):
        d = dict(data)
        d['rr_mean'], d['rr_std'] = tuple(d['rr_mean']), tuple(d['rr_std'])
        return cls(**d)


@dataclass(frozen=True)
class Request:
    session: str
    beat_id: int
    position: int
    rr_samples: int
    sampling_hz: int
    ready_at: int
    model_id: str
    weights_sha256: str
    preprocess_sha256: str
    waveform: tuple
    rr: tuple
    status: str = 'OK'

    def __post_init__(self):
        if not TOKEN.fullmatch(self.session) or not TOKEN.fullmatch(self.model_id):
            raise ValueError('会话/模型ID无效')
        if any(type(x) is not int or not 0 <= x <= 0xffffffff
               for x in (self.beat_id, self.position, self.rr_samples, self.ready_at)):
            raise ValueError('编号须uint32')
        if self.beat_id == 0 or self.position > self.ready_at or self.sampling_hz not in (360, 500):
            raise ValueError('编号/时轴/采样率无效')
        if not SHA.fullmatch(self.weights_sha256) or not SHA.fullmatch(self.preprocess_sha256):
            raise ValueError('模型哈希无效')
        if self.status not in STATES:
            raise ValueError('未知状态')
        if self.status == 'OK':
            if len(self.waveform) != 128 or len(self.rr) != 3 or not self.rr_samples:
                raise ValueError('完整网络输入必须128+3且RR已知')
            if not all(math.isfinite(x) for x in (*self.waveform, *self.rr)) or any(abs(x)>5 for x in self.rr):
                raise ValueError('输入非有限或RR未按合同裁剪')

    @classmethod
    def from_dict(cls, data):
        d = dict(data)
        d['waveform'], d['rr'] = tuple(d['waveform']), tuple(d['rr'])
        return cls(**d)


@dataclass(frozen=True)
class Result:
    request: Request
    status: str
    class_id: int = -1
    valid: bool = False
    accepted: bool = False

    def __post_init__(self):
        if self.status not in STATES or self.valid != (self.status == 'OK'):
            raise ValueError('状态/有效位矛盾')
        if self.valid and self.class_id not in range(4):
            raise ValueError('有效类别须0..3')
        if not self.valid and self.class_id != -1:
            raise ValueError('无效结果不能带已知类别')

    @property
    def label(self):
        return CLASSES[self.class_id] if self.valid else '?'


def normalize_rr(basic, spec):
    import numpy as np
    basic = np.asarray(basic, dtype=np.float32)
    if basic.shape != (3,) or not np.isfinite(basic).all():
        raise ValueError('基础RR形状/数值无效')
    return np.clip((basic - np.asarray(spec.rr_mean, dtype=np.float32)) /
                   np.asarray(spec.rr_std, dtype=np.float32), -5, 5).astype(np.float32)


def prepare(beat, session, beat_id, spec):
    """原窗口函数保持不动；本层补训练折RR标准化和模型身份。"""
    if beat.units_per_mv != 4096:
        raise ValueError('源波形单位未符合当前合同')
    protocol = ROOT / 'model/protocols/cnn_git_v1_protocol.json'
    if digest(protocol) != spec.preprocess_sha256:
        raise ValueError('窗口协议与模型绑定不匹配')
    wave, basic = beat.model_input()
    status = 'MISSING_RR' if basic is None else 'OK'
    rr = () if basic is None else tuple(float(x) for x in normalize_rr(basic, spec))
    return Request(session, beat_id, beat.position, beat.rr_samples, beat.sampling_hz,
                   beat.emitted, spec.model_id, spec.weights_sha256, spec.preprocess_sha256,
                   tuple(float(x) for x in wave), rr, status)


class ClassQueue:
    """有界FIFO和一个in-flight；时钟为调用方单调毫秒，超时含排队。"""
    def __init__(self, spec, capacity=4, timeout_ms=2000):
        if type(capacity) is not int or not 1 <= capacity <= 32 or type(timeout_ms) is not int or timeout_ms < 1:
            raise ValueError('队列/测试超时配置无效')
        self.spec, self.capacity, self.timeout_ms = spec, capacity, timeout_ms
        self.reset('initial')

    def reset(self, session):
        if not TOKEN.fullmatch(session):
            raise ValueError('会话ID无效')
        self.session, self.last_id, self.last_time = session, 0, -1
        self.pending, self.active = deque(), None

    def _clock(self, now):
        if type(now) is not int or now < self.last_time:
            raise ValueError('时钟倒退或无效')
        self.last_time = now

    def submit(self, request, now):
        self._clock(now)
        if (request.session != self.session or request.model_id != self.spec.model_id or
            request.weights_sha256 != self.spec.weights_sha256 or
            request.preprocess_sha256 != self.spec.preprocess_sha256):
            raise ValueError('会话/模型不匹配')
        if request.beat_id <= self.last_id:
            raise ValueError('重复/倒序请求')
        if len(self.pending) + (self.active is not None) >= self.capacity:
            return 'BUSY'
        self.pending.append((request, now + self.timeout_ms))
        self.last_id = request.beat_id
        return 'ACCEPTED'

    def take(self, now):
        self._clock(now)
        if self.active is not None or not self.pending or now >= self.pending[0][1]:
            return None
        self.active = self.pending.popleft()
        return self.active[0]

    def expire(self, now):
        self._clock(now)
        slot = self.active if self.active is not None else (self.pending[0] if self.pending else None)
        if slot is None or now < slot[1]:
            return None
        if self.active is not None:
            self.active = None
        else:
            self.pending.popleft()
        return Result(slot[0], 'TIMEOUT')

    def complete(self, result, now):
        self._clock(now)
        if self.active is None or result.request != self.active[0]:
            raise ValueError('迟到/错会话/错心拍结果')
        if now >= self.active[1]:
            self.active = None
            return Result(result.request, 'TIMEOUT')
        if result.request.status != 'OK' and result.status == 'OK':
            raise ValueError('无效输入不能完成为有效分类')
        if result.valid and result.accepted != self.spec.accepted:
            raise ValueError('模型接受状态不匹配')
        self.active = None
        return result

    def cancel(self, now):
        self._clock(now)
        slots = ([self.active] if self.active else []) + list(self.pending)
        self.active, self.pending = None, deque()
        return [Result(r, 'CANCELLED') for r, _ in slots]


def event_line(result, spec):
    """一次发送E；假后端压为未知，不借演示标签声明CLASS_RESULT。"""
    req = result.request
    if req.model_id != spec.model_id or req.weights_sha256 != spec.weights_sha256:
        raise ValueError('结果身份不匹配')
    label = result.label if spec.kind in ('development', 'accepted') else '?'
    hr = '-1' if not req.rr_samples else f'{60*req.sampling_hz/req.rr_samples:.1f}'
    return f'E,{req.beat_id},{req.position},{req.rr_samples},{hr},{label},-1\n'.encode('ascii')


class TorchBackend:
    """只加载已核SHA的本地失败开发权重作接口检查；不训练/选型。"""
    def __init__(self, fold=0):
        if fold not in (0, 1, 2):
            raise ValueError('开发折无效')
        import torch
        from torch import nn
        from ecg_trainable_cnn import create_model
        base = ROOT / 'model/baseline'
        frozen = json.loads((base / 'manifest_start.json').read_text(encoding='utf-8'))
        source = 'src/reference/ecg_trainable_cnn.py'
        if digest(ROOT / source) != frozen['source_sha256'][source]:
            raise ValueError('冻结模型结构源码哈希不符')
        folder = base / f'residual_verified/fold_{fold}'
        manifest = json.loads((base / 'files.json').read_text(encoding='utf-8'))['files']
        for name in ('best_weights.pt', 'normalization.json'):
            path = folder / name
            relative = path.relative_to(base).as_posix()
            row = next(v for k, v in manifest.items() if k.replace('\\', '/') == relative)
            if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
                raise ValueError('冻结权重/归一化哈希不符')
        norm = json.loads((folder / 'normalization.json').read_text(encoding='utf-8'))
        self.spec = ModelSpec(f'dev-residual-f{fold}', digest(folder / 'best_weights.pt'),
                              digest(ROOT / 'model/protocols/cnn_git_v1_protocol.json'),
                              digest(folder / 'normalization.json'),
                              tuple(norm['rr_mean']), tuple(norm['rr_std']), False, 'development')
        self.model = create_model(dict(family='residual', feature='both', width=16, input_samples=128))
        def remove_bn(module):
            for name, child in list(module.named_children()):
                if isinstance(child, nn.BatchNorm1d):
                    setattr(module, name, nn.Identity())
                else:
                    remove_bn(child)
        remove_bn(self.model)
        self.model.load_state_dict(torch.load(folder / 'best_weights.pt', weights_only=True))
        self.model.eval()
        torch.set_num_threads(2)

    def infer(self, request):
        import torch
        if (request.model_id, request.weights_sha256, request.preprocess_sha256) != (
            self.spec.model_id, self.spec.weights_sha256, self.spec.preprocess_sha256):
            raise ValueError('后端身份不匹配')
        if request.status != 'OK':
            return Result(request, request.status)
        with torch.no_grad():
            out = self.model(torch.tensor([request.waveform], dtype=torch.float32),
                             torch.tensor([request.rr], dtype=torch.float32))
        if out.shape != (1, 4) or not torch.isfinite(out).all():
            return Result(request, 'BACKEND_ERROR')
        return Result(request, 'OK', int(out.argmax(1)[0]), True, self.spec.accepted)


def serve(fold):
    """本地双环境JSONL桥接；不是板卡串口、网络服务或训练入口。"""
    import sys
    backend = TorchBackend(fold)
    print(json.dumps({'ready': True, 'spec': asdict(backend.spec)}), flush=True)
    for line in sys.stdin:
        try:
            req = Request.from_dict(json.loads(line))
            result = backend.infer(req)
            print(json.dumps(asdict(result)), flush=True)
        except Exception as error:
            print(json.dumps({'error': type(error).__name__ + ': ' + str(error)}), flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve-development-fold', type=int, required=True)
    serve(parser.parse_args().serve_development_fold)
