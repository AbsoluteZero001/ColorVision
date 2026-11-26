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

$Version = (& $Python -c "from backend import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Version)) {
    throw "Application version could not be read from backend.__version__."
}

$BuildRoot = Join-Path $ProjectRoot "build"
$DistRoot = Join-Path $ProjectRoot "dist"
$StagingRoot = Join-Path $BuildRoot "release-staging"
$WorkRoot = Join-Path $BuildRoot "pyinstaller-v$Version"
$ExeFileName = "ColorVision-v$Version-win-x64.exe"
$StagedExecutablePath = Join-Path $StagingRoot $ExeFileName
$FinalExecutablePath = Join-Path $DistRoot $ExeFileName
$LegacyDirPath = Join-Path $DistRoot "ColorVision"
$LegacyZipPath = Join-Path $DistRoot "ColorVision-v$Version-win-x64.zip"

function Remove-SafeTree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$AllowedRoot
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullRoot = [System.IO.Path]::GetFullPath($AllowedRoot)
    if (-not $fullRoot.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $fullRoot += [System.IO.Path]::DirectorySeparatorChar
    }
    if (-not $fullPath.StartsWith(
        $fullRoot,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to remove path outside allowed root: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
}

New-Item -ItemType Directory -Force -Path $BuildRoot, $DistRoot | Out-Null
Remove-SafeTree -Path $StagingRoot -AllowedRoot $BuildRoot
Remove-SafeTree -Path $WorkRoot -AllowedRoot $BuildRoot

& $Python -m PyInstaller `
    --clean `
    --noconfirm `
    --distpath $StagingRoot `
    --workpath $WorkRoot `
    $SpecPath
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

if (-not (Test-Path -LiteralPath $StagedExecutablePath -PathType Leaf)) {
    throw "PyInstaller completed without producing the staged single-file EXE: $StagedExecutablePath"
}

$VerifyArchiveScript = @'
import sys
from PyInstaller.archive.readers import CArchiveReader

exe_path = sys.argv[1]
reader = CArchiveReader(exe_path)
entries = {name.replace("\\", "/") for name in reader.toc}

required = ("backend/config/config.json", "frontend/dist/index.html")
for item in required:
    if item not in entries:
        raise SystemExit(f"Missing embedded resource in EXE: {item}")

assets = [name for name in entries if name.startswith("frontend/dist/assets/")]
if not assets:
    raise SystemExit("Missing embedded Vue assets under frontend/dist/assets/")

print(f"Verified {len(entries)} embedded archive entries ({len(assets)} frontend asset(s)).")
'@

$VerifyArchiveScript | & $Python - $StagedExecutablePath
if ($LASTEXITCODE -ne 0) {
    throw "Embedded resource verification failed for $StagedExecutablePath"
}

if (Test-Path -LiteralPath $LegacyDirPath) {
    Remove-SafeTree -Path $LegacyDirPath -AllowedRoot $DistRoot
}
if (Test-Path -LiteralPath $LegacyZipPath -PathType Leaf) {
    Remove-Item -LiteralPath $LegacyZipPath -Force
}

Copy-Item -LiteralPath $StagedExecutablePath -Destination $FinalExecutablePath -Force

if (-not (Test-Path -LiteralPath $FinalExecutablePath -PathType Leaf)) {
    throw "Final single-file EXE is missing: $FinalExecutablePath"
}

Remove-SafeTree -Path $StagingRoot -AllowedRoot $BuildRoot
Remove-SafeTree -Path $WorkRoot -AllowedRoot $BuildRoot

$Executable = Get-Item -LiteralPath $FinalExecutablePath
$SizeMb = [Math]::Round($Executable.Length / 1MB, 2)
$Hash = (Get-FileHash -LiteralPath $FinalExecutablePath -Algorithm SHA256).Hash

Write-Host "ColorVision version: $Version"
Write-Host "ColorVision EXE: $FinalExecutablePath"
Write-Host "ColorVision EXE size: $SizeMb MB ($($Executable.Length) bytes)"
Write-Host "ColorVision EXE SHA-256: $Hash"
