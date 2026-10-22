param(
    [Parameter(Mandatory=$true)][string]$VitisBin,
    [string]$CableSerial,
    [string]$ServerUrl = 'TCP:127.0.0.1:3121',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$manifest = Get-Content -LiteralPath (Join-Path $root 'manifest.json') -Raw | ConvertFrom-Json
foreach ($entry in $manifest.files.PSObject.Properties) {
    $path = Join-Path $root $entry.Name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {throw "文件缺失: $path"}
    if ((Get-Item -LiteralPath $path).Length -ne $entry.Value.bytes -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.sha256) {
        throw "文件校验失败: $path"
    }
}
if ($CheckOnly) {Write-Host 'CHECK_ONLY_PASS: 文件校验通过，没有连接板卡'; return}
if (-not $CableSerial) {throw '先核对下载器序列号，并通过-CableSerial明确指定'}
$tool = Join-Path $VitisBin 'xsdb.bat'
if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {throw "找不到工具: $tool"}
$runOutput = & $tool (Join-Path $PSScriptRoot 'run_bridge.tcl') $CableSerial $ServerUrl 2>&1
$runOutput | Write-Output
if ($LASTEXITCODE -ne 0 -or -not ($runOutput -match '^ECG_BRIDGE_JTAG_STARTED')) {
    throw 'JTAG未完成，保留上方错误；不能只按工具退出码判定成功'
}
