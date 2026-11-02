param([Parameter(Mandatory=$true)][string]$VitisBin,[Parameter(Mandatory=$true)][string]$Python,[Parameter(Mandatory=$true)][string]$Parameters,[Parameter(Mandatory=$true)][string]$Output,[switch]$Cosim)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$out=[IO.Path]::GetFullPath((Join-Path $root $Output))
$rom=[IO.Path]::GetFullPath((Join-Path $root $Parameters))
if (!$out.StartsWith((Join-Path $root 'tmp')+[IO.Path]::DirectorySeparatorChar)) {throw '输出必须位于tmp'}
if(Test-Path -LiteralPath $out){throw '输出目录已存在'}
& $Python (Join-Path $root 'build/export_cnn_hls.py') --output $rom
if($LASTEXITCODE -ne 0){throw '权重导出失败'}
$source=(Join-Path $root 'src/hls/ecg_cnn/cnn_hls.cpp').Replace('\','/')
$bench=(Join-Path $root 'sim/cnn_hls_tb.cpp').Replace('\','/')
$config=Join-Path $rom 'hls_config.cfg'
@("part=xc7z020clg400-2","[hls]","flow_target=vivado","syn.top=cnn_hls","syn.file=$source","syn.cflags=-I$($rom.Replace('\','/')) -ffp-contract=off","tb.file=$bench","tb.cflags=-I$($rom.Replace('\','/'))","clock=10","cosim.tool=xsim") | Set-Content -LiteralPath $config -Encoding ascii
& (Join-Path $VitisBin 'v++.bat') --compile --mode hls --config $config --work_dir $out
if($LASTEXITCODE -ne 0){throw 'HLS综合失败'}
if($Cosim){
    & (Join-Path $VitisBin 'vitis-run.bat') --mode hls --cosim --config $config --work_dir $out
    if($LASTEXITCODE -ne 0){throw 'RTL联合仿真失败'}
}
