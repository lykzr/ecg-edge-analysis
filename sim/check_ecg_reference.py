"""生成确定性输入，逐周期比较 Python 与真实 RTL；无需板卡。"""
import argparse
import csv
import hashlib
import json
import os
import random
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/reference"))
from ecg_reference import Config, Detector, State, replay


def samples_with_idle(samples):
    frames = [(0, 0, 0)] * 3
    for i, sample in enumerate(samples):
        frames.append((1, 1, sample))
        # 单个样本之后的空拍也参与比较，覆盖阈值输出的后一拍更新。
        frames.extend([(1, 0, sample)] * (i % 3))
    return frames


def random_frames(config, count, seed):
    rng = random.Random(seed)
    limit = 1 << (config.sample_width - 1)
    choices = [-limit, limit - 1, 0, 1, -1]
    result = [(0, 0, 0)] * 3
    for i in range(count):
        sample = rng.choice(choices) if i % 3 else rng.randrange(-limit, limit)
        result.append((0 if i in (611, 1255) else 1, int(rng.random() > 0.25), sample))
    return result


def command(args, directory, log_name):
    with (directory / log_name).open("w", encoding="utf-8") as log:
        subprocess.run([str(x) for x in args], cwd=directory, stdout=log,
                       stderr=subprocess.STDOUT, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)


def compare_case(name, config, frames, output, bin_dir):
    directory = output / name
    directory.mkdir()
    (directory / "vectors.txt").write_text(
        "".join(f"{r} {v} {s}\n" for r, v, s in frames), encoding="ascii")
    with (directory / "input.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["reset_n", "valid", "sample"])
        writer.writerows(frames)
    params = ", ".join(f".{key.upper()}({value})" for key, value in asdict(config).items())
    wrapper = directory / "tb_reference.sv"
    wrapper.write_text(f"module tb_reference; ecg_reference_driver #({params}) driver(); endmodule\n",
                       encoding="ascii")
    suffix = ".bat" if os.name == "nt" else ""
    command([bin_dir / ("xvlog" + suffix), "-sv", ROOT / "src/rtl/ecg_qrs_detector.sv",
             ROOT / "sim/tb_ecg_reference.sv", wrapper], directory, "compile.log")
    command([bin_dir / ("xelab" + suffix), "tb_reference", "-s", "reference_snapshot", "-mt", "off"],
            directory, "elaborate.log")
    command([bin_dir / ("xsim" + suffix), "reference_snapshot", "-runall"], directory, "simulation.log")
    sim_log = (directory / "simulation.log").read_text(encoding="utf-8", errors="replace")
    if "PASS REFERENCE_TRACE" not in sim_log or "Fatal:" in sim_log or "ERROR:" in sim_log:
        raise AssertionError(f"{name}: 仿真未完整结束")

    summary = replay(directory / "input.csv", directory / "python", config)
    with (directory / "rtl_trace.csv").open(newline="") as f:
        rtl = list(csv.DictReader(f))
    if len(rtl) != len(frames):
        raise AssertionError(f"{name}: RTL 周期数 {len(rtl)} != 输入周期数 {len(frames)}")
    detector = Detector(config)
    events = []
    with (directory / "comparison.csv").open("w", encoding="utf-8", newline="") as f:
        comparison = csv.writer(f)
        comparison.writerow(["cycle", "matching_fields"])
        for cycle, ((reset_n, valid, sample), row) in enumerate(zip(frames, rtl)):
            expected = asdict(detector.tick(sample, bool(valid), bool(reset_n)))
            for key, value in expected.items():
                actual = int(row[key])
                if actual != value:
                    raise AssertionError(f"{name} cycle={cycle} {key}: RTL={actual} Python={value}; "
                                         f"input={frames[cycle]}")
            comparison.writerow([cycle, len(expected)])
            if expected["qrs_valid"]:
                events.append((expected["qrs_sample_index"], expected["rr_interval_samples"]))
    if name == "smoke_waveform":
        golden = [(79 + 360 * i, 0 if i == 0 else 360) for i in range(16)]
        if events != golden:
            raise AssertionError("smoke 合成输入未得到手工推导的 16 个事件")
    result = dict(name=name, config=asdict(config), cycles=len(frames), fields=len(State.__dataclass_fields__),
                  events=summary["events"], result="PASS")
    print(f"PASS {name}: {len(frames)} cycles, {result['fields']} fields, {summary['events']} events", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vivado-bin", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "tmp/reference_check")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError("输出目录已存在，请选新目录，避免覆盖")
    output.mkdir(parents=True)
    samples = [0] * 100
    for i in range(16):
        samples += [20000 if i % 2 == 0 else -20000] + [0] * 359
    configurations = [
        ("smoke_waveform", Config(), samples_with_idle(samples)),
        ("random_360", Config(), random_frames(Config(), 2400, 114)),
        ("random_500", Config(sample_rate_hz=500),
         random_frames(Config(sample_rate_hz=500), 2400, 115)),
        ("window_one_zero_levels", Config(sample_width=8, sample_rate_hz=1000,
          integration_ms=0, refractory_ms=0, initial_noise_level=0, initial_signal_level=0),
         samples_with_idle([0]*20 + [127,-128,0]*180 + [0]*20)),
        ("energy_wrap", Config(sample_rate_hz=1000, integration_ms=9, refractory_ms=4,
          energy_width=12, initial_noise_level=4000, initial_signal_level=100),
         random_frames(Config(energy_width=12), 2400, 116)),
        ("noise_above_signal_32", Config(energy_width=32, initial_noise_level=16,
          initial_signal_level=8), samples_with_idle([0]*50 + [20000,0]*150 + [0]*60)),
    ]
    results = [compare_case(name, config, frames, output, args.vivado_bin.resolve())
               for name, config, frames in configurations]
    sources = ["src/rtl/ecg_qrs_detector.sv", "src/reference/ecg_reference.py",
               "sim/tb_ecg_reference.sv", "sim/check_ecg_reference.py"]
    report = dict(result="PASS", cases=results, total_cycles=sum(x["cycles"] for x in results),
                  source_hashes={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
                  scope="detector cycle/state agreement; no AXI/FIFO/clinical accuracy validation",
                  smoke_board_test="NOT_TESTED", board_used=False)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS ECG_REFERENCE_ALL_CASES", flush=True)


if __name__ == "__main__":
    main()
