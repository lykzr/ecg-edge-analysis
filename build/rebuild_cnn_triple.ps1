param(
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$Vitis,
    [Parameter(Mandatory=$true)][string]$Vivado,
    [string]$Name='cnn_triple_rebuild',
    [switch]$FastWorkLed,
    [switch]$Int8Fast,
    [switch]$Conv16
)
$ErrorActionPreference='Stop'
if($Int8Fast -and !$FastWorkLed){throw 'Int8Fast需要FastWorkLed'}
if($Conv16 -and !$Int8Fast){throw 'Conv16需要Int8Fast'}
$root=Split-Path $PSScriptRoot -Parent
if($Name -notmatch '^[A-Za-z0-9_-]+$'){throw 'Name仅允许英文字母、数字、下划线和短横线'}
$base=Join-Path $root "tmp/$Name"
if(Test-Path -LiteralPath $base){throw '输出目录已存在，请换Name，原文件不覆盖'}
New-Item -ItemType Directory -Path $base | Out-Null
function Invoke-Checked([string]$program,[string[]]$arguments){
    & $program @arguments
    if($LASTEXITCODE -ne 0){throw "执行失败：$program；保留输出供检查"}
}
Push-Location $root
try {
    $rel="tmp/$Name"
    Invoke-Checked $Python @('build/export_hgb_pl.py','--output',"$rel/hgb")
    $fpScript=if($FastWorkLed){'run_cnn_fast_hls.ps1'}else{'run_cnn_hls.ps1'}
    $plScript=if($FastWorkLed){'build/build_cnn_fast_pl.tcl'}else{'build/build_cnn_int8_pl.tcl'}
    if($Int8Fast){$plScript='build/build_cnn_int8_fast_pl.tcl'}
    & "$PSScriptRoot/$fpScript" -VitisBin "$Vitis/bin" -Python $Python -Parameters "$rel/fp32_params" -Output "$rel/fp32_hls" -Cosim
    if($Int8Fast){
        & "$PSScriptRoot/run_cnn_int8_fast_hls.ps1" -VitisBin "$Vitis/bin" -Python $Python -Parameters "$rel/int8_params" -Output "$rel/int8_hls" -Cosim -Conv16:$Conv16
    } else {
        Invoke-Checked $Python @('build/export_cnn_int8.py','--output',"$rel/int8_params")
        & "$PSScriptRoot/run_cnn_int8_hls.ps1" -VitisBin "$Vitis/bin" -Parameters "$rel/int8_params" -Output "$rel/int8_hls" -Cosim
    }
    Invoke-Checked "$Vivado/bin/vivado.bat" @('-mode','batch','-source',$plScript,'-tclargs',"$rel/hardware","$rel/hgb","$rel/fp32_hls/hls/impl/ip","$rel/int8_hls/hls/impl/ip")
    $env:ECG_CNN_PL='1'
    $env:ECG_CNN_INT8='1'
    $env:ECG_ACTIVITY_LED=if($FastWorkLed){'1'}else{'0'}
    $env:ECG_CNN_INT8_FAST=if(!$Int8Fast){'0'}elseif($Conv16){'16'}else{'4'}
    $env:ECG_CNN_PARAMETERS="$base/fp32_params/arm"
    $env:ECG_CNN_INT8_PARAMETERS="$base/int8_params"
    $env:ECG_CNN_HARDWARE="$base/hardware"
    $env:ECG_HGB_PL_ROM="$base/hgb"
    $env:ECG_CNN_WORKSPACE="$base/vitis"
    $env:ECG_ARM_GCC="$Vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-gcc.exe"
    Invoke-Checked "$Vitis/bin/vitis.bat" @('-s','board/build_cnn_arm.py')
    Write-Output "重建结束：$base/hardware/cnn_pl.xpr；加载清单：$base/vitis/build_manifest.json。尚未连接或下载板卡。"
} finally { Pop-Location }
