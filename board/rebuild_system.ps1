param(
    [Parameter(Mandatory=$true)][string]$Output,
    [Parameter(Mandatory=$true)][string]$VivadoBin,
    [Parameter(Mandatory=$true)][string]$VitisBin,
    [Parameter(Mandatory=$true)][string]$Python,
    [ValidateSet(360,500)][int]$Rate=360,
    [ValidateSet(0,1)][int]$Trace=0
)
# 在原生PowerShell进程直接调用Vivado，避免Python包装的层次解析差异。
$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outputRoot=[IO.Path]::GetFullPath((Join-Path $projectRoot $Output))
$tmpRoot=[IO.Path]::GetFullPath((Join-Path $projectRoot 'tmp'))+[IO.Path]::DirectorySeparatorChar
if (!$outputRoot.StartsWith($tmpRoot,[StringComparison]::OrdinalIgnoreCase)) {throw '输出必须在项目tmp内'}
if (Test-Path -LiteralPath $outputRoot) {throw '输出目录已存在，禁止覆盖'}
$pythonExe=(Get-Item -LiteralPath $Python).FullName
$vivadoExe=(Get-Item -LiteralPath (Join-Path $VivadoBin 'vivado.bat')).FullName
$vitisDir=(Get-Item -LiteralPath $VitisBin).FullName
New-Item -ItemType Directory -Path $outputRoot | Out-Null
$priorTmp=$env:TMP; $priorTemp=$env:TEMP; $priorLocal=$env:XILINX_LOCAL_USER_DATA
$priorLocation=Get-Location
try {
    $env:TMP=$outputRoot; $env:TEMP=$outputRoot; $env:XILINX_LOCAL_USER_DATA='no'
    Set-Location -LiteralPath $outputRoot
    & $vivadoExe -mode batch -log vivado_tool.log -journal vivado_tool.jou -source (Join-Path $projectRoot 'build/rebuild_system.tcl') -tclargs (Join-Path $outputRoot 'hardware_build') *> (Join-Path $outputRoot 'vivado_stdout.log')
    if ($LASTEXITCODE -ne 0) {throw 'Vivado阶段失败，保留日志'}
    & $pythonExe -B (Join-Path $projectRoot 'board/rebuild_system.py') --output (Join-Path $outputRoot 'sw') --vivado-bin $VivadoBin --vitis-bin $vitisDir --rate $Rate --trace $Trace --hardware-from (Join-Path $outputRoot 'hardware_build/hardware') *> (Join-Path $outputRoot 'software_stdout.log')
    if ($LASTEXITCODE -ne 0) {throw '软件或匹配核验失败，保留日志'}
    $summary=Get-Content -LiteralPath (Join-Path $outputRoot 'sw/summary.json') -Raw | ConvertFrom-Json
    if (!$summary.passed -or $summary.sampling_hz -ne $Rate) {throw '完整构建摘要不符'}
    $summary | Add-Member -NotePropertyName entrypoint -NotePropertyValue 'board/rebuild_system.ps1'
    $summary | Add-Member -NotePropertyName hardware_built_in_this_invocation -NotePropertyValue $true
    $summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $outputRoot 'summary.json') -Encoding UTF8
    Write-Output ('PASS FULL_REBUILD rate='+$Rate+'; no board operation; '+$outputRoot)
} finally {
    Set-Location -LiteralPath $priorLocation.Path
    $env:TMP=$priorTmp; $env:TEMP=$priorTemp; $env:XILINX_LOCAL_USER_DATA=$priorLocal
}
