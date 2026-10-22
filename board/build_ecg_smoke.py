"""在独立 tmp 工作区构建 PS ECG 自检，保护现有工程与发布镜像。"""
import os
import hashlib
from pathlib import Path
import vitis

root = Path(__file__).resolve().parents[1]
workspace = Path(os.environ.get("ECG_SMOKE_WORKSPACE", str(root / "tmp/ecg_smoke/vitis_workspace"))).resolve()
xsa = Path(os.environ.get("ECG_SMOKE_XSA", str(root / "releases/latest/smoke/hardware/ecg_system_candidate.xsa"))).resolve()
source = root / "src/ps/ecg_smoke/main.c"
if workspace.exists():
    raise RuntimeError("工作区已存在；请使用 ECG_SMOKE_WORKSPACE 指定新的空目录，避免覆盖")
for path in (xsa, source):
    if not path.is_file():
        raise FileNotFoundError(path)
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
client = vitis.create_client()
try:
    client.set_workspace(str(workspace))
    platform = client.create_platform_component(
        name="ecg_platform", hw_design=str(xsa), os="standalone",
        cpu="ps7_cortexa9_0", domain_name="standalone_ps7_cortexa9_0")
    platform.build()
    app = client.create_app_component(
        name="ecg_smoke", platform=client.find_platform_in_repos("ecg_platform"),
        domain="standalone_ps7_cortexa9_0", template="empty_application")
    app.import_files(from_loc=str(source.parent), files=["main.c"])
    app.build()
    # 2026.1 import_files 默认复制到组件根，UserConfig.cmake 引用 ../main.c。
    copied = workspace / "ecg_smoke/main.c"
    if hashlib.sha256(copied.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError("构建源文件与正式源文件不一致")
    print("ECG_SMOKE_BUILD_PASS", flush=True)
    print("WORKSPACE=" + str(workspace), flush=True)
finally:
    vitis.dispose()
