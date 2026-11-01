param([string]$VivadoBin, [string]$Python, [string]$Output='tmp/hgb_pl_sim_02')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
if (!$VivadoBin -or !$Python) { throw '请指定-VivadoBin及-Python' }
& $Python (Join-Path $root 'build/export_hgb_pl.py') --output (Join-Path $root $Output)
if($LASTEXITCODE -ne 0){throw '参数导出失败'}
Push-Location (Join-Path $root $Output)
try {
    & (Join-Path $VivadoBin 'xvlog.bat') --sv -i . (Join-Path $root 'src/rtl/ecg_hgb_core.sv') (Join-Path $root 'src/rtl/ecg_hgb_axi_lite.sv') (Join-Path $root 'sim/ecg_hgb_core_tb.sv') (Join-Path $root 'sim/ecg_hgb_axi_tb.sv')
    if($LASTEXITCODE -ne 0){throw '编译失败'}
    & (Join-Path $VivadoBin 'xelab.bat') work.ecg_hgb_core_tb -s hgb_core_sim --debug typical
    if($LASTEXITCODE -ne 0){throw '展开失败'}
    & (Join-Path $VivadoBin 'xsim.bat') hgb_core_sim -runall 2>&1 | Tee-Object simulation.log
    if($LASTEXITCODE -ne 0 -or (Get-Content simulation.log -Raw) -notmatch 'PASS HGB PL core'){throw '仿真未通过'}
    & (Join-Path $VivadoBin 'xelab.bat') work.ecg_hgb_axi_tb -s hgb_axi_sim --debug typical
    if($LASTEXITCODE -ne 0){throw 'AXI展开失败'}
    & (Join-Path $VivadoBin 'xsim.bat') hgb_axi_sim -runall 2>&1 | Tee-Object axi_simulation.log
    if($LASTEXITCODE -ne 0 -or (Get-Content axi_simulation.log -Raw) -notmatch 'PASS HGB AXI'){throw 'AXI仿真未通过'}
} finally {Pop-Location}
