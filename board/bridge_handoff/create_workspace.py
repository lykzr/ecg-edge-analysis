"""在完整系统交付包中重建bridge工作区；由Vitis Python执行，不连接板卡。"""
import argparse
import os
from pathlib import Path
import runpy


def configuration(root):
    root = Path(root).resolve()
    paths = dict(ECG_STREAM_XSA=root/'bridge/hardware/ecg_system_candidate.xsa',
                 ECG_STREAM_BIT=root/'bridge/hardware/ecg_system_candidate.bit',
                 ECG_STREAM_PSINIT=root/'bridge/hardware/ps7_init.tcl',
                 ECG_STREAM_LAUNCH_TEMPLATE=root/'smoke/board/launch_template.json')
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    return {name:str(path) for name,path in paths.items()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    # 本文件发布时位于系统包board/create_bridge_workspace.py。
    root=Path(__file__).resolve().parents[1]
    values=configuration(root)
    if args.check_only:
        print('CHECK_ONLY_PASS: 相对硬件/模板路径存在，不构建、不连接板卡')
    else:
        os.environ.update(values)
        os.environ['ECG_STREAM_WORKSPACE']=str((args.workspace or root/'tmp/ecg_bridge/vitis_workspace').resolve())
        runpy.run_path(str(root/'board/build_ecg_bridge.py'),run_name='__main__')
