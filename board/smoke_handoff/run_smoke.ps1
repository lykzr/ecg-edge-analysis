param(
    [Parameter(Mandatory=$true)][string]$VitisBin,
    [string]$ServerUrl = 'TCP:127.0.0.1:3121',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$kitRoot = Split-Path $PSScriptRoot -Parent
$manifest = Get-Content -LiteralPath (Join-Path $kitRoot 'manifest.json') -Raw | ConvertFrom-Json
foreach ($entry in $manifest.files.PSObject.Properties) {
    $file = Join-Path $kitRoot $entry.Name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "文件缺失: $file" }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.sha256) { throw "文件校验失败: $file" }
}
Write-Host '包内文件 SHA256 校验通过'
if ($CheckOnly) { Write-Host 'CHECK_ONLY_PASS：没有连接或操作板卡'; return }
$tool = Join-Path $VitisBin 'xsdb.bat'
if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "找不到 $tool；请使用带 Tcl XSDB 的 AMD 工具安装。" }
Push-Location $kitRoot
try {
    & $tool 'board/run_smoke.tcl' $ServerUrl 2>&1 | Tee-Object -Variable runOutput
    if ($LASTEXITCODE -ne 0 -or -not ($runOutput -match '^JTAG launched;')) { throw "JTAG 启动未完成，退出码 $LASTEXITCODE；请查看上方输出和串口。" }
} finally { Pop-Location }
