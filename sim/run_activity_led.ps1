param([Parameter(Mandatory=$true)][string]$VivadoBin,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$out=[IO.Path]::GetFullPath((Join-Path $root $Output))
if(!$out.StartsWith((Join-Path $root 'tmp')+[IO.Path]::DirectorySeparatorChar)){throw '输出必须在tmp'}
if(Test-Path -LiteralPath $out){throw '输出目录已存在'}
New-Item -ItemType Directory -Path $out | Out-Null
Push-Location $out
try {
    & "$VivadoBin/xvlog.bat" -sv "$root/src/rtl/ecg_activity_led.sv" "$root/sim/activity_led_tb.sv" *> compile.log
    if($LASTEXITCODE -ne 0){throw '工作灯编译失败'}
    & "$VivadoBin/xelab.bat" activity_led_tb -s activity_snapshot -mt off *> elaborate.log
    if($LASTEXITCODE -ne 0){throw '工作灯展开失败'}
    & "$VivadoBin/xsim.bat" activity_snapshot -runall *> simulation.log
    if($LASTEXITCODE -ne 0 -or !(Select-String -LiteralPath simulation.log -Pattern 'PASS ACTIVITY_LED' -Quiet)){throw '工作灯仿真失败'}
    Write-Output 'PASS ACTIVITY_LED'
} finally {Pop-Location}
