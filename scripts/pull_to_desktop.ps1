# Sync middleware version workbook from repository to Desktop\ztx
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceFile = Join-Path $repoRoot "ztx\中间件版本信息.xlsx"
$desktopDir = Join-Path $env:USERPROFILE "Desktop\ztx"
$targetFile = Join-Path $desktopDir "中间件版本信息.xlsx"

if (-not (Test-Path $sourceFile)) {
    Write-Error "Source file not found: $sourceFile. Run scripts/fetch_middleware_versions.py first."
}

New-Item -ItemType Directory -Force -Path $desktopDir | Out-Null
Copy-Item -Path $sourceFile -Destination $targetFile -Force

Write-Host "Copied middleware version report to $targetFile"
