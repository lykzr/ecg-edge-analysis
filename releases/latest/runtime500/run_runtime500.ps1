# 按包内SHA256核对后临时JTAG下载；不写Flash、不修改系统执行策略。
[CmdletBinding()]
param([string]$Xsdb = '', [string]$CableSerial = '', [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Get-PackageHash([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}
$base = [IO.Path]::GetFullPath($PSScriptRoot)
$manifestPath = Join-Path $base 'manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.sampling_hz -ne 500 -or $manifest.window_trace -ne $false) { throw '不是正常500Hz发布组合' }
foreach ($entry in $manifest.files.PSObject.Properties) {
    $name = $entry.Name
    if ($name.Contains('\') -or $name.Contains(':') -or $name.StartsWith('/') -or ($name.Split('/') -contains '..')) { throw ('清单路径无效：' + $name) }
    $path = [IO.Path]::GetFullPath((Join-Path $base $name))
    if (-not $path.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw '清单路径越界' }
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('缺少文件：' + $name) }
    if ((Get-Item -LiteralPath $path).Length -ne $entry.Value.bytes) { throw ('字节数不符：' + $name) }
    if ((Get-PackageHash $path) -ne $entry.Value.sha256) { throw ('SHA256不符：' + $name) }
}
Write-Host ('文件核对通过；构建ID：' + $manifest.build_id)
if ($CheckOnly) { Write-Host '仅核对文件，未连接或复位板卡。'; return }
if (-not $Xsdb -and $env:XILINX_VITIS) { $Xsdb = Join-Path $env:XILINX_VITIS 'bin/xsdb.bat' }
if (-not $Xsdb) {
    $command = Get-Command xsdb.bat -ErrorAction SilentlyContinue
    if ($command) { $Xsdb = $command.Source }
}
if (-not $Xsdb -or -not (Test-Path -LiteralPath $Xsdb -PathType Leaf)) {
    $Xsdb = (Read-Host '填写已安装的Vitis/bin/xsdb.bat完整路径').Trim('"')
}
if (-not (Test-Path -LiteralPath $Xsdb -PathType Leaf)) { throw 'XSDB不存在；未连接板卡' }
if (-not $CableSerial) { $CableSerial = Read-Host '填写已核实的唯一JTAG下载器序列号' }
if ($CableSerial -notmatch '^[A-Za-z0-9_-]+$') { throw '下载器序列号格式错误' }
function Test-HardwareServer {
    $socket = New-Object Net.Sockets.TcpClient
    try {
        $task = $socket.ConnectAsync('127.0.0.1', 3121)
        if (-not $task.Wait(500)) { return $false }
        return $socket.Connected
    } catch { return $false } finally { $socket.Dispose() }
}
if (-not (Test-HardwareServer)) {
    $server = Join-Path (Split-Path -Parent $Xsdb) 'hw_server.bat'
    if (-not (Test-Path -LiteralPath $server -PathType Leaf)) { throw '未找到匹配hw_server.bat；请从Vitis启动硬件服务后重试' }
    Write-Host '正在后台启动同版本硬件服务。'
    Start-Process -FilePath $server -WorkingDirectory ([IO.Path]::GetTempPath()) -WindowStyle Hidden
    for ($i = 0; $i -lt 20 -and -not (Test-HardwareServer); $i++) { Start-Sleep -Milliseconds 250 }
    if (-not (Test-HardwareServer)) { throw '硬件服务未在3121就绪；未下载板卡' }
}
Write-Host '请关闭占用串口的终端。正在临时JTAG下载；不写Flash。'
& $Xsdb (Join-Path $base 'run_runtime500.tcl') $CableSerial
if ($LASTEXITCODE -ne 0) { throw ('下载失败，XSDB退出码：' + $LASTEXITCODE) }
Write-Host '下载完成。打开客户端，在送样/双向中转窗口选择板卡端口后开始。'
Write-Host '掉电、复位或一轮会话结束后，需重新下载再开始。'
