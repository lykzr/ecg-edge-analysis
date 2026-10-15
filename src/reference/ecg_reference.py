"""ecg_qrs_detector.sv 的逐周期整数参考模型；不模拟 AXI 或事件 FIFO。"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    sample_width: int = 16
    sample_rate_hz: int = 360
    integration_ms: int = 120
    refractory_ms: int = 200
    energy_width: int = 24
    initial_noise_level: int = 4096
    initial_signal_level: int = 16384

    def __post_init__(self):
        if not 2 <= self.sample_width <= 16 or not 1 <= self.energy_width <= 32:
            raise ValueError("模型支持采样位宽 2..16、能量位宽 1..32")
        if self.sample_rate_hz <= 0 or min(self.integration_ms, self.refractory_ms) < 0:
            raise ValueError("采样率必须为正，时长不能为负")
        if max(self.sample_rate_hz * self.integration_ms,
               self.sample_rate_hz * self.refractory_ms) > 0x7FFFFFFF:
            raise ValueError("参数乘积超出 RTL 32 位 integer 的范围")
        if not all(0 <= n <= 0x7FFFFFFF for n in
                   (self.initial_noise_level, self.initial_signal_level)):
            raise ValueError("初始估计必须是非负 32 位 signed integer")

    @property
    def window_length(self):
        return max(1, self.sample_rate_hz * self.integration_ms // 1000)

    @property
    def refractory_length(self):
        return max(1, self.sample_rate_hz * self.refractory_ms // 1000)


@dataclass(frozen=True)
class State:
    qrs_valid: int
    qrs_sample_index: int
    rr_interval_samples: int
    integrated_energy: int
    adaptive_threshold: int
    noise_level: int
    signal_level: int
    previous_energy: int
    previous_sample: int
    previous_sample_valid: int
    sample_index: int
    refractory_remaining: int
    write_pointer: int
    last_qrs_index: int
    have_last_qrs: int


class Detector:
    def __init__(self, config: Config = Config()):
        self.config = config
        self.mask = (1 << config.energy_width) - 1
        self.reset()

    def reset(self):
        c = self.config
        self.history = [0] * c.window_length
        self.previous_sample = self.previous_sample_valid = 0
        self.sample_index = self.write_pointer = 0
        self.last_qrs_index = self.have_last_qrs = 0
        self.refractory_remaining = 0
        self.integrated_energy = self.previous_energy = 0
        self.noise_level = c.initial_noise_level & self.mask
        self.signal_level = c.initial_signal_level & self.mask
        # RTL integer 参数参与复位表达式：32 位逻辑右移，不用 Python 负数算术右移。
        difference = (c.initial_signal_level - c.initial_noise_level) & 0xFFFFFFFF
        self.adaptive_threshold = (c.initial_noise_level + (difference >> 2)) & self.mask
        self.qrs_valid = self.qrs_sample_index = self.rr_interval_samples = 0
        return self.snapshot()

    def snapshot(self):
        return State(**{name: int(getattr(self, name)) for name in State.__dataclass_fields__})

    def tick(self, sample: int = 0, valid: bool = True, reset_n: bool = True) -> State:
        """一个上升沿后的状态；valid=False 不推进采样位置/不应期。"""
        if not reset_n:
            return self.reset()
        limit = 1 << (self.config.sample_width - 1)
        if not -limit <= sample < limit:
            raise ValueError(f"有符号 {self.config.sample_width} 位样本越界：{sample}")

        # 全部组合值用旧状态计算，再应用对应的非阻塞赋值。
        threshold = self.noise_level
        if self.signal_level > self.noise_level:
            threshold += (self.signal_level - self.noise_level) >> 2
        threshold = (threshold & self.mask) or 1
        self.adaptive_threshold = threshold
        self.qrs_valid = 0
        if not valid:
            return self.snapshot()

        old_index = self.sample_index
        old_sample = self.previous_sample
        had_sample = self.previous_sample_valid
        self.sample_index = (old_index + 1) & 0xFFFFFFFF
        self.previous_sample = sample
        if not had_sample:
            self.previous_sample_valid = 1
            return self.snapshot()

        absolute_difference = abs(sample - old_sample)
        derivative_term = absolute_difference & self.mask
        energy = (self.integrated_energy - self.history[self.write_pointer]
                  + derivative_term) & self.mask
        old_energy = self.previous_energy
        old_refractory = self.refractory_remaining
        self.history[self.write_pointer] = absolute_difference
        self.write_pointer = (self.write_pointer + 1) % self.config.window_length
        self.integrated_energy = self.previous_energy = energy
        if old_refractory:
            self.refractory_remaining = old_refractory - 1

        if old_energy < threshold <= energy and old_refractory == 0:
            corrected = max(0, old_index - self.config.window_length // 2)
            self.qrs_valid = 1
            self.qrs_sample_index = corrected
            if self.have_last_qrs:
                self.rr_interval_samples = (corrected - self.last_qrs_index) & 0xFFFFFFFF
            self.last_qrs_index = corrected
            self.have_last_qrs = 1
            self.refractory_remaining = self.config.refractory_length - 1
            self.signal_level = (self.signal_level - (self.signal_level >> 3)
                                 + (energy >> 3)) & self.mask
        elif energy < threshold:
            self.noise_level = (self.noise_level - (self.noise_level >> 3)
                                + (energy >> 3)) & self.mask
        return self.snapshot()


def replay(input_path: Path, output_dir: Path, config: Config):
    """CSV 一行代表一个时钟：sample 必填，valid/reset_n 默认 1。"""
    if output_dir.exists():
        raise FileExistsError("输出目录已存在，停止避免覆盖")
    with input_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or "sample" not in reader.fieldnames:
            raise ValueError("输入 CSV 必须有 sample 列，可选 valid、reset_n")
        output_dir.mkdir(parents=True)
        detector = Detector(config)
        with (output_dir / "trace.csv").open("w", encoding="utf-8", newline="") as trace_file, \
             (output_dir / "events.csv").open("w", encoding="utf-8", newline="") as event_file:
            fields = ["cycle", "reset_n", "valid", "sample", *State.__dataclass_fields__]
            trace = csv.DictWriter(trace_file, fieldnames=fields)
            events = csv.DictWriter(event_file, fieldnames=["cycle", "index", "rr_samples"])
            trace.writeheader()
            events.writeheader()
            cycles = event_count = 0
            for cycle, row in enumerate(reader):
                sample = int(row["sample"])
                valid = int(row.get("valid", "1"))
                reset_n = int(row.get("reset_n", "1"))
                if valid not in (0, 1) or reset_n not in (0, 1):
                    raise ValueError(f"第 {cycle + 2} 行 valid/reset_n 必须为 0 或 1")
                state = detector.tick(sample, bool(valid), bool(reset_n))
                trace.writerow(dict(cycle=cycle, sample=sample, valid=valid,
                                    reset_n=reset_n, **asdict(state)))
                if state.qrs_valid:
                    event_count += 1
                    events.writerow(dict(cycle=cycle, index=state.qrs_sample_index,
                                         rr_samples=state.rr_interval_samples))
                cycles += 1
        summary = dict(config=asdict(config), window_length=config.window_length,
                       refractory_length=config.refractory_length,
                       cycles=cycles, events=event_count, input=str(input_path.resolve()),
                       scope="integer detector only; no AXI/FIFO or accuracy validation",
                       smoke_board_test="NOT_TESTED")
        (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    for field in Config.__dataclass_fields__:
        parser.add_argument("--" + field.replace("_", "-"), type=int,
                            default=getattr(Config(), field))
    args = parser.parse_args()
    config = Config(**{field: getattr(args, field) for field in Config.__dataclass_fields__})
    print(json.dumps(replay(args.input, args.output_dir, config), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
