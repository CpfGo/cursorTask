# Pull middleware version Excel from repository to local Desktop\ztx folder.
param(
    [string]$RepoUrl = "https://github.com/CpfGo/cursorTask.git",
    [string]$Branch = "main",
    [string]$TargetDir = "$env:USERPROFILE\Desktop\ztx"
)

$ErrorActionPreference = "Stop"
$FileName = "中间件版本信息.xlsx"
$TempDir = Join-Path $env:TEMP "cursorTask-middleware-sync"

Write-Host "Syncing $FileName to $TargetDir ..."

if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

if (Test-Path $TempDir) {
    Remove-Item -Recurse -Force $TempDir
}

git clone --depth 1 --branch $Branch $RepoUrl $TempDir | Out-Null

$SourceFile = Join-Path $TempDir "ztx\$FileName"
if (-not (Test-Path $SourceFile)) {
    throw "Repository file not found: ztx/$FileName"
}

Copy-Item -Path $SourceFile -Destination (Join-Path $TargetDir $FileName) -Force
Remove-Item -Recurse -Force $TempDir

Write-Host "Done. File saved to $(Join-Path $TargetDir $FileName)"
