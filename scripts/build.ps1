[CmdletBinding()]
param(
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$FrontendDist = Join-Path $FrontendRoot "dist"
$FrontendIndex = Join-Path $FrontendDist "index.html"
$FrontendAssets = Join-Path $FrontendDist "assets"
$SpecPath = Join-Path $ProjectRoot "colorvision.spec"

if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) {
    throw "Frontend dependencies not found. Run npm install in the frontend directory first."
}

Push-Location $FrontendRoot
try {
    npm run build
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend build failed."
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $FrontendIndex -PathType Leaf)) {
    throw "Vue production entry was not generated: $FrontendIndex"
}

$AssetFiles = @(Get-ChildItem -LiteralPath $FrontendAssets -File -Recurse -ErrorAction SilentlyContinue)
if (-not (Test-Path -LiteralPath $FrontendAssets -PathType Container) -or $AssetFiles.Count -eq 0) {
    throw "Vue production assets were not generated: $FrontendAssets"
}

if ($FrontendOnly) {
    Write-Host "Frontend build completed with verified Vue production assets."
    exit 0
}

if (-not (Test-Path -LiteralPath $SpecPath)) {
    throw "colorvision.spec is not available yet. PyInstaller packaging has not been implemented."
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment not found."
}

& $Python -m PyInstaller --clean --noconfirm $SpecPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$ExecutablePath = Join-Path $ProjectRoot "dist\ColorVision\ColorVision.exe"
if (-not (Test-Path -LiteralPath $ExecutablePath)) {
    throw "PyInstaller completed without producing ColorVision.exe."
}

$Executable = Get-Item -LiteralPath $ExecutablePath
$SizeMb = [Math]::Round($Executable.Length / 1MB, 2)
$ReadmePath = Join-Path $ProjectRoot "README.md"
$OutputRoot = Join-Path $ProjectRoot "dist\ColorVision"
$BundledFrontendRoot = Join-Path $OutputRoot "_internal\frontend\dist"
$BundledIndex = Join-Path $BundledFrontendRoot "index.html"
$BundledAssets = Join-Path $BundledFrontendRoot "assets"
$BundledAssetFiles = @(Get-ChildItem -LiteralPath $BundledAssets -File -Recurse -ErrorAction SilentlyContinue)

if (-not (Test-Path -LiteralPath $BundledIndex -PathType Leaf)) {
    throw "Packaged Vue entry is missing: $BundledIndex"
}

if (-not (Test-Path -LiteralPath $BundledAssets -PathType Container) -or $BundledAssetFiles.Count -eq 0) {
    throw "Packaged Vue assets are missing or empty: $BundledAssets"
}

if (Test-Path -LiteralPath $ReadmePath) {
    Copy-Item -LiteralPath $ReadmePath -Destination (Join-Path $OutputRoot "README.md") -Force
}
Write-Host "ColorVision EXE: $($Executable.FullName)"
Write-Host "ColorVision EXE size: $SizeMb MB"
