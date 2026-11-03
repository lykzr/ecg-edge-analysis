param([string]$OutputDirectory)
$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if(-not $OutputDirectory){$OutputDirectory=Join-Path $projectRoot ('tmp/report_tex_build_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))}
$buildDirectory=[IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $buildDirectory -Force | Out-Null
$engine=Get-Command xelatex -ErrorAction Stop
Push-Location (Join-Path $projectRoot 'report')
try {
    for($pass=1;$pass -le 2;$pass++) {
        & $engine.Source -interaction=nonstopmode -halt-on-error "-output-directory=$buildDirectory" report.tex *> (Join-Path $buildDirectory "pass_$pass.txt")
        if($LASTEXITCODE -ne 0){throw "TeX编译失败，见 $buildDirectory/pass_$pass.txt"}
    }
    $log=Get-Content -LiteralPath (Join-Path $buildDirectory 'report.log') -Raw
    if($log -match 'Missing character:|Overfull \\[hv]box'){throw "存在缺字或越界，见 $buildDirectory/report.log"}
    Write-Output (Join-Path $buildDirectory 'report.pdf')
} finally {Pop-Location}
# 仅生成供核看的PDF，不自动覆盖正式稿，旧稿由维护者归档后替换。
