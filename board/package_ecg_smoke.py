"""构造可拷贝的 smoke 候选工程包，拒绝覆盖；不运行板卡/Flash。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PINNED = {
    'src/ps/ecg_smoke/main.c': '149fcf44ffff8f42f9d917a85f4b063803f2c87091b23e444fad284589e2216a',
    'releases/latest/smoke/prebuilt/ecg_smoke.elf': '2e573ba9a9244cd4a9ef0f5ce80eca8957e1b512594b9b9389fc616353285bf7',
    'releases/latest/smoke/hardware/ecg_system_candidate.bit': 'd6471189437faa4dd3ffb402c4a8cff2f3b39a5349ba836a7a61f33273f50cfb',
    'releases/latest/smoke/hardware/ecg_system_candidate.xsa': 'fea241041311c9b40b0db9806c66a6ada2175b84c84ff571f72de2efd7bc6248',
    'releases/latest/smoke/hardware/ps7_init.tcl': '02fa20dccd77fc2e5517a57d810289b2003afd3b82884a96723a7f9e968657f9',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.relative_to(ROOT / 'tmp')
    archive = output.with_suffix('.zip')
    if output.exists() or archive.exists():
        raise FileExistsError('目标已存在，选择新的输出目录')
    for source, expected in PINNED.items():
        if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != expected:
            raise RuntimeError('冻结 smoke 组合发生变化，重新验证后才能打包: ' + source)
    mapping = {
        'src/ps/ecg_smoke/main.c': 'src/ps/ecg_smoke/main.c',
        'prebuilt/ecg_smoke.elf': 'releases/latest/smoke/prebuilt/ecg_smoke.elf',
        'hardware/ecg_system_candidate.bit': 'releases/latest/smoke/hardware/ecg_system_candidate.bit',
        'hardware/ecg_system_candidate.xsa': 'releases/latest/smoke/hardware/ecg_system_candidate.xsa',
        'hardware/ps7_init.tcl': 'releases/latest/smoke/hardware/ps7_init.tcl',
        'board/build_ecg_smoke.py': 'board/build_ecg_smoke.py',
        'board/launch_template.json': 'releases/latest/smoke/board/launch_template.json',
        'LICENSE': 'LICENSE',
    }
    for name in ['create_workspace.py', 'create_workspace.ps1', 'run_smoke.ps1', 'run_smoke.tcl', 'capture_uart.ps1']:
        mapping['board/' + name] = 'board/smoke_handoff/' + name
    mapping['README.md'] = 'board/smoke_handoff/README.md.in'
    output.mkdir(parents=True)
    entries = {}
    for target, source in mapping.items():
        destination = output / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / source, destination)
        entries[target] = {'source': source}
    # 不复制包含其他模型/数据库相对链接的项目总来源表。
    (output / 'third_party.md').write_text(
        '# 许可说明\n\n自有 smoke 源码和脚本适用 LICENSE。AMD Vivado/Vitis 2026.1 '
        '生成的 bit、XSA、ps7_init.tcl 和含 BSP 的 ELF 保留 AMD 及相关组件原有权利，'
        '不由根 MIT 重新授权。构建依赖接收方合法安装的 AMD 工具。此包用于团队内部板级验证，'
        '公开发布前仍需核对最终组件的源码/许可交付要求。未包含原厂手册、安装器、数据集。\n', encoding='utf-8')
    entries['third_party.md'] = {'source': 'generated license boundary'}
    (output / 'expected_uart.txt').write_text(
        'BEGIN ECG_SMOKE base=0x43C00000\nCONFIG rate=360 window_ms=120 refractory_ms=200\n'
        'PASS CONFIG\nPASS ZERO_INPUT\nEVENT seq=1 index=79 rr=0\n'
        'EVENT seq=2 index=439 rr=360\nEVENT seq=3 index=799 rr=360\n'
        'EVENT seq=4 index=1159 rr=360\nPASS EVENT_FIELDS_AND_POP\n'
        'PASS FIFO_OVERFLOW queued=8 total=16 dropped=4\n'
        'PASS FIFO_DRAIN_AND_OVERFLOW_CLEAR\nPASS ECG_SMOKE failures=0\n', encoding='utf-8')
    entries['expected_uart.txt'] = {'source': 'expected key lines; not measured output'}
    for name, entry in entries.items():
        payload = (output / name).read_bytes()
        entry.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    manifest = dict(schema=1, purpose='Navigator V2 Zynq-7020 ECG smoke JTAG handoff',
                    tool_version='Vivado/Vitis 2026.1', board_execution='NOT_TESTED',
                    flash_programming='NOT_PERFORMED', files=entries)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                bundle.write(path, str(Path(output.name) / path.relative_to(output)))
    print(json.dumps(dict(package=str(output), archive=str(archive), bytes=archive.stat().st_size,
                          sha256=hashlib.sha256(archive.read_bytes()).hexdigest()), indent=2))


if __name__ == '__main__':
    main()
