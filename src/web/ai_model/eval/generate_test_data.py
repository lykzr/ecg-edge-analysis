#!/usr/bin/env python3
"""
生成测试数据集脚本

生成用于模型评估的合成 ECG 数据。

用法:
    python generate_test_data.py --type clean --output data/eval_clean --count 100
    python generate_test_data.py --type noise --output data/eval_noise --count 100
"""

import argparse
import numpy as np
from pathlib import Path
from datetime import datetime


def generate_clean_ecg(duration_sec: float = 10, sample_rate: int = 500) -> np.ndarray:
    """生成干净的 ECG 信号"""
    n_samples = int(duration_sec * sample_rate)
    t = np.arange(n_samples) / sample_rate

    # 基础心率 72 BPM
    heart_rate = 72
    rr_interval = 60 / heart_rate

    signal = np.zeros(n_samples)

    # 生成 5 个心动周期
    for cycle in range(5):
        start_idx = int(cycle * rr_interval * sample_rate)
        if start_idx >= n_samples:
            break

        # 简化 PQRST 波形
        p_wave = 0.25 * np.exp(-((t - start_idx/sample_rate - 0.1) ** 2) / 0.002)
        qrs = 1.5 * np.exp(-((t - start_idx/sample_rate - 0.15) ** 2) / 0.0004)
        t_wave = 0.35 * np.exp(-((t - start_idx/sample_rate - 0.3) ** 2) / 0.003)

        signal += p_wave + qrs + t_wave

    return signal


def add_noise(signal: np.ndarray, noise_level: float = 0.1) -> np.ndarray:
    """添加噪声"""
    noise = np.random.normal(0, noise_level, len(signal))

    # 添加基线漂移
    baseline = 0.2 * np.sin(2 * np.pi * 0.1 * np.arange(len(signal)) / len(signal))

    # 添加工频干扰
    powerline = 0.1 * np.sin(2 * np.pi * 50 * np.arange(len(signal)) / 500)

    return signal + noise + baseline + powerline


def save_ecg_data(signal: np.ndarray, output_path: Path, lead_type: str = "single"):
    """保存 ECG 数据"""
    data = {
        "lead_type": lead_type,
        "sample_rate": 500,
        "duration_sec": len(signal) / 500,
        "timestamp": datetime.utcnow().isoformat(),
        "signal": signal.tolist()
    }

    import json
    with open(output_path, 'w') as f:
        json.dump(data, f)

    print(f"  Saved: {output_path.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate test ECG data")
    parser.add_argument("--type", required=True, choices=["clean", "noise"])
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--count", type=int, default=100, help="Number of samples to generate")

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.count} {args.type} ECG samples...")

    for i in range(args.count):
        signal = generate_clean_ecg()

        if args.type == "noise":
            signal = add_noise(signal, noise_level=0.15)

        filename = f"ecg_{args.type}_{i:04d}.json"
        save_ecg_data(signal, output_dir / filename)

    print(f"\n✅ Generated {args.count} samples in {output_dir}")

    # 生成 README
    readme = f"""# 评估数据集 - {args.type.upper()}

生成了 {args.count} 个合成 ECG 样本。

## 数据格式

```json
{{
  "lead_type": "single",
  "sample_rate": 500,
  "duration_sec": 10.0,
  "timestamp": "ISO8601",
  "signal": [0.0, 0.1, ...]
}}
```

## 生成参数

- 类型: {args.type}
- 样本数: {args.count}
- 采样率: 500 Hz
- 时长: 10 秒/样本
- 生成时间: {datetime.utcnow().isoformat()}
"""

    (output_dir / "README.md").write_text(readme)
