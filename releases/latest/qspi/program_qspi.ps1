# 默认只核对文件；只有显式-Program才写QSPI。不改系统权限或启动寄存器。
[CmdletBinding()]
param([string]$Xsdb='', [string]$ProgramFlash='', [string]$CableSerial='', [switch]$Program, [switch]$CheckOnly)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if ($Program -and $CheckOnly) {throw 'Program与CheckOnly不能同时指定'}
function Get-PackageHash([string]$Path) {
 $sha=[Security.Cryptography.SHA256]::Create();$stream=[IO.File]::OpenRead($Path)
 try {return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
 finally {$stream.Dispose();$sha.Dispose()}
}
$base=[IO.Path]::GetFullPath($PSScriptRoot)
$meta=Get-Content -LiteralPath (Join-Path $base 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($entry in $meta.files.PSObject.Properties) {
 $name=$entry.Name
 if ($name.Contains('\') -or $name.Contains(':') -or $name.StartsWith('/') -or ($name.Split('/') -contains '..')) {throw '非法清单路径'}
 $path=Join-Path $base $name
 if ((Get-Item -LiteralPath $path).Length -ne $entry.Value.bytes -or (Get-PackageHash $path) -ne $entry.Value.sha256) {throw ('QSPI文件校验失败：'+$name)}
}
$packageRoot=[IO.Path]::GetFullPath((Join-Path $base '..'))
foreach ($entry in $meta.components.PSObject.Properties) {
 $name=$entry.Value.path
 if ($name.Contains('\') -or $name.Contains(':') -or $name.StartsWith('/') -or ($name.Split('/') -contains '..')) {throw '非法组成路径'}
 $path=Join-Path $packageRoot $name
 if ((Get-Item -LiteralPath $path).Length -ne $entry.Value.bytes -or (Get-PackageHash $path) -ne $entry.Value.sha256) {throw ('QSPI组成校验失败：'+$name)}
}
if ($meta.offset -ne 0 -or $meta.flash_type -ne 'qspi-x4-single') {throw '不是已核实的QSPI合同'}
$blob=[IO.File]::ReadAllBytes((Join-Path $base 'BOOT.BIN'))
if ($blob.Length -lt 40 -or $blob.Length -gt 33554432 -or [BitConverter]::ToUInt32($blob,32) -ne [Convert]::ToUInt32('aa995566',16) -or [BitConverter]::ToUInt32($blob,36) -ne 0x584c4e58) {throw '启动镜像头或容量错误'}
Write-Host ('QSPI文件核对通过；构建ID：'+$meta.build_id)
if (-not $Program) {Write-Host '未指定-Program，仅核对文件，未连接或写入板卡。';return}
if (-not (Test-Path -LiteralPath $Xsdb -PathType Leaf) -or -not (Test-Path -LiteralPath $ProgramFlash -PathType Leaf)) {throw '请指定已有XSDB与ProgramFlash路径'}
if ($CableSerial -notmatch '^[A-Za-z0-9_-]+$') {throw '须指定已核实的下载器序列号'}
$possibleRoot=[IO.Path]::GetFullPath((Join-Path $base '../../..'))
$parent=if (Test-Path -LiteralPath (Join-Path $possibleRoot 'AGENTS.md')) {Join-Path $possibleRoot 'tmp'} else {[IO.Path]::GetTempPath()}
$logs=Join-Path $parent ('qspi_write_'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $logs | Out-Null
$prior=Get-Location
try {
 Set-Location -LiteralPath $logs
 # program_flash从可写目录运行，避免安装目录临时文件失败。
 $listener=[Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object {$_.Port -eq 3121}
 if (-not $listener) {
  $server=Join-Path (Split-Path -Parent $Xsdb) 'hw_server.bat'
  if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {throw '缺少同工具目录的hw_server'}
  Start-Process -FilePath $env:ComSpec -ArgumentList ('/c ""'+$server+'" -s tcp::3121"') -WorkingDirectory $logs -WindowStyle Hidden | Out-Null
  Start-Sleep -Seconds 3
 }
 $probe=@(& $Xsdb (Join-Path $base 'probe_qspi.tcl') $CableSerial 0 2>&1)
 $probe | Set-Content -LiteralPath (Join-Path $logs 'identity.log')
 if ($LASTEXITCODE -ne 0) {throw '未确认唯一板卡/JTAG启动模式，未写Flash'}
 $targets=@($probe | Where-Object {"$_" -match '^FLASH_TARGET='})
 if ($targets.Count -ne 1) {throw '目标身份不唯一，未写Flash'}
 $target="$($targets[0])".Substring(13)
 Write-Host '即将覆盖QSPI偏移0的镜像区域，不执行整片擦除。请保持供电。'
 & $ProgramFlash -f (Join-Path $base 'BOOT.BIN') -fsbl (Join-Path $base 'fsbl.elf') -offset 0x0 -flash_type qspi-x4-single -verify -target_name $target -url TCP:127.0.0.1:3121 *> (Join-Path $logs 'program_flash.log')
 if ($LASTEXITCODE -ne 0) {throw ('编程失败，保留日志：'+$logs)}
 $text=Get-Content -LiteralPath (Join-Path $logs 'program_flash.log') -Raw
 if ($text -notmatch 'Verify Operation successful' -or $text -notmatch 'Flash Operation Successful') {throw '未得到编程及校验成功证据'}
 Write-Host '写入和校验完成。断电，BOOT_CFG设QSPI（1=ON、2=OFF），彻底掉电后上电再验收。'
 Write-Host ('日志目录：'+$logs)
} finally {Set-Location -LiteralPath $prior.Path}
