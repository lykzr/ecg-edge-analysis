param([string]$VivadoBin='D:/AMDDesignTools/2026.1/Vivado/bin')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$testDir=Join-Path $projectRoot 'tmp/rtl_tests'
$null=New-Item -ItemType Directory -Path $testDir -Force
Push-Location -LiteralPath $testDir
try {
    & (Join-Path $VivadoBin 'xvlog.bat') -sv (Join-Path $projectRoot 'rtl/ecg_qrs_detector.sv') (Join-Path $projectRoot 'rtl/ecg_qrs_axi_lite.sv') (Join-Path $projectRoot 'tests/tb_axi_lite.sv')
    if($LASTEXITCODE -ne 0){throw 'HDL 编译失败'}
    & (Join-Path $VivadoBin 'xelab.bat') tb_axi_lite -s tb_axi_lite_snapshot -mt off
    if($LASTEXITCODE -ne 0){throw '仿真 elaboration 失败'}
    & (Join-Path $VivadoBin 'xsim.bat') tb_axi_lite_snapshot -runall
    if($LASTEXITCODE -ne 0){throw '仿真进程失败'}
    $log=Get-Content -LiteralPath 'xsim.log' -Raw
    if($log -notmatch 'PASS AXI split channels' -or $log -match '(?m)^ERROR:|Fatal:') {throw '仿真没有通过全部检查，查看 tmp/rtl_tests/xsim.log'}
    Write-Output 'RTL 接口自检通过；没有上板，也未验证真实 ECG 检测精度。'
} finally { Pop-Location }
