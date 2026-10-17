param(
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$PortName,
    [ValidateRange(1,3600)][int]$Seconds = 90,
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$LogPath,
    [switch]$CheckOnly
)
# 从板上通过包的被动串口采集脚本合并：显式端口、禁止覆盖、失败/超时非零退出。
$ErrorActionPreference = 'Stop'
$absoluteLog = [System.IO.Path]::GetFullPath($LogPath)
if (Test-Path -LiteralPath $absoluteLog) { throw "日志已存在，不覆盖：$absoluteLog" }
$parent = Split-Path $absoluteLog -Parent
if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw "日志父目录不存在：$parent" }
if ($CheckOnly) {
    Write-Output "CHECK_ONLY_PASS：参数有效；未打开串口、未创建日志；$PortName 115200 8N1"
    return
}
$serial = [System.IO.Ports.SerialPort]::new($PortName, 115200, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
$serial.Handshake = [System.IO.Ports.Handshake]::None
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.Encoding = [System.Text.Encoding]::ASCII
$writer = $null
$stream = $null
$received = ''
$completed = $false
try {
    $serial.Open()
    # CreateNew避免检查与创建之间的并发覆盖；只读串口，不发送命令。
    $stream = [System.IO.FileStream]::new($absoluteLog, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
    $writer = [System.IO.StreamWriter]::new($stream, [System.Text.UTF8Encoding]::new($false))
    $writer.AutoFlush = $true
    Write-Output "UART_CAPTURE_READY $PortName 115200 8N1 log=$absoluteLog"
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    while ($watch.Elapsed.TotalSeconds -lt $Seconds) {
        $chunk = $serial.ReadExisting()
        if ($chunk.Length -gt 0) {
            $writer.Write($chunk)
            $received += $chunk
            Write-Output $chunk
            if ($received -match '(?m)^(PASS|FAIL) ECG_SMOKE failures=\d+[\t \r]*$') {
                $completed = $true
                break
            }
        }
        Start-Sleep -Milliseconds 50
    }
    if (-not $completed) { throw 'UART_CAPTURE_TIMEOUT_WITHOUT_FINAL_RESULT：日志已保留' }
    if ($received -match '(?m)^FAIL\b' -or $received -notmatch '(?m)^PASS ECG_SMOKE failures=0[\t \r]*$') {
        throw 'UART_CAPTURE_SMOKE_FAILED：日志已保留'
    }
    Write-Output 'UART_CAPTURE_FINAL_PASS_RECEIVED：仍须核对完整预期关键行'
} finally {
    if ($serial.IsOpen) { $serial.Close() }
    $serial.Dispose()
    if ($null -ne $writer) { $writer.Dispose() }
    elseif ($null -ne $stream) { $stream.Dispose() }
}
