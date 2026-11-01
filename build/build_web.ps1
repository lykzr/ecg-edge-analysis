param([switch]$SkipInstall)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot  = Join-Path $projectRoot 'src/web/frontend'
$workRoot    = Join-Path $projectRoot 'tmp/web_frontend'

# 保留已有依赖和本地历史；SkipInstall不能先删掉node_modules。
# 正式输入在下面同步，构建产物仍由Vite写到tmp，不自动清空工作区。
New-Item -ItemType Directory -Force $workRoot | Out-Null

# 仅同步正式输入；依赖、Vite 临时文件和 dist 始终留在 tmp
Get-ChildItem -LiteralPath $sourceRoot -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName `
              -Destination (Join-Path $workRoot $_.Name) `
              -Force
}
Copy-Item -LiteralPath (Join-Path $sourceRoot 'src') `
          -Destination $workRoot `
          -Recurse -Force

$env:npm_config_cache = Join-Path $projectRoot 'tmp/npm_cache'

Push-Location $workRoot
try {
    if (-not $SkipInstall) {
        & npm.cmd ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw '前端依赖安装失败' }
    }

    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw '前端检查或构建失败' }
}
finally {
    Pop-Location
}
