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
$OutputRoot = Join-Path $DistRoot "ColorVision"
$StagingRoot = Join-Path $BuildRoot "release-staging"
$WorkRoot = Join-Path $BuildRoot "pyinstaller-v$Version"
$StagedOutputRoot = Join-Path $StagingRoot "ColorVision"
$ZipPath = Join-Path $DistRoot "ColorVision-v$Version-win-x64.zip"

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

$ExecutablePath = Join-Path $StagedOutputRoot "ColorVision.exe"
if (-not (Test-Path -LiteralPath $ExecutablePath)) {
    throw "PyInstaller completed without producing the staged ColorVision.exe."
}

$Executable = Get-Item -LiteralPath $ExecutablePath
$SizeMb = [Math]::Round($Executable.Length / 1MB, 2)
$ReadmePath = Join-Path $ProjectRoot "README.md"
$BundledFrontendRoot = Join-Path $StagedOutputRoot "_internal\frontend\dist"
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
    Copy-Item -LiteralPath $ReadmePath -Destination (Join-Path $StagedOutputRoot "README.md") -Force
}

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive `
    -Path (Join-Path $StagedOutputRoot "*") `
    -DestinationPath $ZipPath `
    -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
    throw "Versioned release ZIP was not generated: $ZipPath"
}

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
foreach ($Item in Get-ChildItem -LiteralPath $StagedOutputRoot -Force) {
    if ($Item.Name -in @("config", "data")) {
        continue
    }

    $TargetPath = Join-Path $OutputRoot $Item.Name
    if (Test-Path -LiteralPath $TargetPath) {
        Remove-SafeTree -Path $TargetPath -AllowedRoot $OutputRoot
    }
    Copy-Item `
        -LiteralPath $Item.FullName `
        -Destination $TargetPath `
        -Recurse `
        -Force
}

$FinalExecutablePath = Join-Path $OutputRoot "ColorVision.exe"
if (-not (Test-Path -LiteralPath $FinalExecutablePath -PathType Leaf)) {
    throw "Final ColorVision.exe is missing: $FinalExecutablePath"
}

$FinalBundledIndex = Join-Path $OutputRoot "_internal\frontend\dist\index.html"
if (-not (Test-Path -LiteralPath $FinalBundledIndex -PathType Leaf)) {
    throw "Final packaged Vue entry is missing: $FinalBundledIndex"
}

Remove-SafeTree -Path $StagingRoot -AllowedRoot $BuildRoot
Remove-SafeTree -Path $WorkRoot -AllowedRoot $BuildRoot

Write-Host "ColorVision version: $Version"
Write-Host "ColorVision EXE: $FinalExecutablePath"
Write-Host "ColorVision EXE size: $SizeMb MB"
Write-Host "ColorVision ZIP: $ZipPath"
