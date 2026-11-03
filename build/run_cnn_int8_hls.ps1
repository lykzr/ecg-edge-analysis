param([Parameter(Mandatory=$true)][string]$VitisBin,[string]$Parameters='tmp/cnn_int8_parameters_01',[string]$Output='tmp/cnn_int8_hls_01',[switch]$Cosim)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$rom=[IO.Path]::GetFullPath((Join-Path $root $Parameters))
$out=[IO.Path]::GetFullPath((Join-Path $root $Output))
if(!$out.StartsWith((Join-Path $root 'tmp')+[IO.Path]::DirectorySeparatorChar)){throw '输出必须位于tmp'}
if(Test-Path -LiteralPath $out){throw '输出目录已存在'}
$source=(Join-Path $root 'src/hls/ecg_cnn_int8/cnn_int8_hls.cpp').Replace('\','/')
$bench=(Join-Path $root 'sim/cnn_int8_hls_tb.cpp').Replace('\','/')
$config=Join-Path $rom 'hls_int8_config.cfg'
@('part=xc7z020clg400-2','[hls]','flow_target=vivado','syn.top=cnn_int8_hls',"syn.file=$source","syn.cflags=-I$($rom.Replace('\','/')) -ffp-contract=off","tb.file=$bench","tb.cflags=-I$($rom.Replace('\','/'))",'clock=10','cosim.tool=xsim') | Set-Content -LiteralPath $config -Encoding ascii
& (Join-Path $VitisBin 'v++.bat') --compile --mode hls --config $config --work_dir $out
if($LASTEXITCODE -ne 0){throw 'INT8 HLS综合失败'}
if($Cosim){
    & (Join-Path $VitisBin 'vitis-run.bat') --mode hls --cosim --config $config --work_dir $out
    if($LASTEXITCODE -ne 0){throw 'INT8 RTL联合仿真失败'}
}
