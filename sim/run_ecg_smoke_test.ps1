param(
    [Parameter(Mandatory=$true)][string]$VivadoBin,
    [string]$OutputDir
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
if(-not $OutputDir){$OutputDir=Join-Path $projectRoot 'tmp/ecg_smoke/rtl_check'}
if(Test-Path -LiteralPath $OutputDir){throw '输出目录已存在，请指定新的 OutputDir，避免覆盖日志'}
New-Item -ItemType Directory -Path $OutputDir | Out-Null
Push-Location -LiteralPath $OutputDir
try {
    & (Join-Path $VivadoBin 'xvlog.bat') -sv (Join-Path $projectRoot 'src/rtl/ecg_qrs_detector.sv') (Join-Path $projectRoot 'src/rtl/ecg_qrs_axi_lite.sv') (Join-Path $projectRoot 'sim/tb_ecg_smoke.sv') *> compile.log
    if($LASTEXITCODE -ne 0){throw 'HDL 编译失败'}
    & (Join-Path $VivadoBin 'xelab.bat') tb_ecg_smoke -s ecg_smoke_snapshot -mt off *> elaborate.log
    if($LASTEXITCODE -ne 0){throw '仿真 elaboration 失败'}
    & (Join-Path $VivadoBin 'xsim.bat') ecg_smoke_snapshot -runall *> simulation.log
    if($LASTEXITCODE -ne 0){throw '仿真进程失败'}
    $log=Get-Content -LiteralPath simulation.log -Raw
    if($log -notmatch 'PASS ECG_SMOKE real samples' -or $log -match '(?m)^ERROR:|Fatal:'){throw '自检未通过，查看 simulation.log'}
    Write-Output 'ECG 合成样本与 FIFO 自检仿真通过；尚未上板。'
} finally {Pop-Location}
