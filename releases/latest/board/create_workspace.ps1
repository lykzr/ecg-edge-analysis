param([Parameter(Mandatory=$true)][string]$VitisBin)
$ErrorActionPreference = 'Stop'
$tool = Join-Path $VitisBin 'vitis.bat'
if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "找不到 $tool" }
$kitRoot = Split-Path $PSScriptRoot -Parent
if ($kitRoot -match '[^\x21-\x7e]') { throw 'Vitis 工作区路径必须使用无空格的英文路径，例如 D:\ecg_smoke_kit。请重新解压。' }
if (Test-Path -LiteralPath (Join-Path $kitRoot 'workspace')) { throw 'workspace 已存在，避免覆盖，请重新解压到另一个目录。' }
Push-Location $kitRoot
try {
    & $tool -s 'board/create_workspace.py'
    if ($LASTEXITCODE -ne 0) { throw "Vitis 构建失败，退出码 $LASTEXITCODE" }
    foreach ($required in @('workspace/ecg_smoke/build/ecg_smoke.elf', 'workspace/ecg_smoke/_ide/launch.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $kitRoot $required) -PathType Leaf)) { throw "构建未完成，缺少 $required；请检查上方日志。" }
    }
} finally { Pop-Location }
