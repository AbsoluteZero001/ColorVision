[CmdletBinding()]
param(
    [switch]$FrontendOnly,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$FrontendDist = Join-Path $FrontendRoot "dist"
$FrontendIndex = Join-Path $FrontendDist "index.html"
$FrontendAssets = Join-Path $FrontendDist "assets"
$SpecPath = Join-Path $ProjectRoot "colorvision.spec"
$InstallerScriptPath = Join-Path $ProjectRoot "installer\ColorVision.iss"

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
    throw "colorvision.spec is missing."
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
$InstallerStagingRoot = Join-Path $BuildRoot "installer-staging"
$WorkRoot = Join-Path $BuildRoot "pyinstaller-v$Version"
$StagedAppRoot = Join-Path $StagingRoot "ColorVision"
$StagedExePath = Join-Path $StagedAppRoot "ColorVision.exe"
$StagedInternalDir = Join-Path $StagedAppRoot "_internal"
$FinalBundleRoot = Join-Path $DistRoot "ColorVision"
$FinalExecutablePath = Join-Path $FinalBundleRoot "ColorVision.exe"
$InstallerOutputPath = Join-Path $DistRoot "ColorVision_Setup.exe"

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

function Write-DefaultConfigFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ConfigDir,
        [Parameter(Mandatory = $true)]
        [string]$InstallDirValue,
        [Parameter(Mandatory = $true)]
        [string]$AppVersion
    )

    New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
    $SeedScript = @'
import json
import sys
from pathlib import Path

config_dir = Path(sys.argv[1])
install_dir_value = sys.argv[2]
app_version = sys.argv[3]
bundled_path = Path(sys.argv[4])

raw = json.loads(bundled_path.read_text(encoding="utf-8"))

app_payload = {
    "app_name": "ColorVision",
    "version": app_version,
    "install_dir": install_dir_value,
    "port": int(raw.get("port", 8000)),
    "image_retention_days": int(raw.get("image_retention_days", 0)),
    "max_image_count": int(raw.get("max_image_count", 0)),
    "log_enabled": bool(raw.get("log_enabled", True)),
    "log_image_storage_enabled": bool(raw.get("log_image_storage_enabled", True)),
    "log_retention_days": int(raw.get("log_retention_days", 0)),
    "max_log_count": int(raw.get("max_log_count", 0)),
}
api_payload = {
    "api_url": str(raw.get("api_url", "http://127.0.0.1:9000/api/color")),
    "token": str(raw.get("token", "")),
    "auto_upload": bool(raw.get("auto_upload", False)),
    "mock_mode": bool(raw.get("mock_mode", True)),
    "timeout": float(raw.get("timeout", 10.0)),
}
camera_payload = {
    "camera_id": str(raw.get("camera_id", "CAM-001")),
}

for name, payload in (
    ("app.json", app_payload),
    ("api-config.json", api_payload),
    ("camera.json", camera_payload),
):
    (config_dir / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
'@
    $BundledConfig = Join-Path $ProjectRoot "backend\config\config.json"
    $SeedScript | & $Python - $ConfigDir $InstallDirValue $AppVersion $BundledConfig
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to generate default configuration files in $ConfigDir"
    }
}

function Find-InnoSetupCompiler {
    $cmd = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
    }
    return $null
}

New-Item -ItemType Directory -Force -Path $BuildRoot, $DistRoot | Out-Null
Remove-SafeTree -Path $StagingRoot -AllowedRoot $BuildRoot
Remove-SafeTree -Path $InstallerStagingRoot -AllowedRoot $BuildRoot
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

if (-not (Test-Path -LiteralPath $StagedExePath -PathType Leaf)) {
    throw "PyInstaller completed without producing ColorVision.exe: $StagedExePath"
}
if (-not (Test-Path -LiteralPath $StagedInternalDir -PathType Container)) {
    throw "PyInstaller completed without producing _internal directory: $StagedInternalDir"
}

$RequiredBundled = @(
    (Join-Path $StagedInternalDir "backend\config\config.json"),
    (Join-Path $StagedInternalDir "frontend\dist\index.html")
)
foreach ($Item in $RequiredBundled) {
    if (-not (Test-Path -LiteralPath $Item -PathType Leaf)) {
        throw "Missing bundled resource under _internal: $Item"
    }
}
$BundledAssets = @(Get-ChildItem -LiteralPath (Join-Path $StagedInternalDir "frontend\dist\assets") -File -Recurse -ErrorAction SilentlyContinue)
if ($BundledAssets.Count -eq 0) {
    throw "Missing bundled Vue assets under _internal\frontend\dist\assets"
}

# Prepare clean installer staging layout (no developer test data/logs)
New-Item -ItemType Directory -Force -Path $InstallerStagingRoot | Out-Null
Copy-Item -LiteralPath $StagedExePath -Destination (Join-Path $InstallerStagingRoot "ColorVision.exe") -Force
Copy-Item -LiteralPath $StagedInternalDir -Destination (Join-Path $InstallerStagingRoot "_internal") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination (Join-Path $InstallerStagingRoot "README.md") -Force
Write-DefaultConfigFiles `
    -ConfigDir (Join-Path $InstallerStagingRoot "config") `
    -InstallDirValue "__COLORVISION_INSTALL_DIR__" `
    -AppVersion $Version

# Refresh clean portable bundle in dist/ColorVision (preserving existing user config/data/cache/logs if present)
New-Item -ItemType Directory -Force -Path $FinalBundleRoot | Out-Null
Copy-Item -LiteralPath $StagedExePath -Destination $FinalExecutablePath -Force
$TargetInternal = Join-Path $FinalBundleRoot "_internal"
if (Test-Path -LiteralPath $TargetInternal) {
    Remove-SafeTree -Path $TargetInternal -AllowedRoot $FinalBundleRoot
}
Copy-Item -LiteralPath $StagedInternalDir -Destination $TargetInternal -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination (Join-Path $FinalBundleRoot "README.md") -Force

foreach ($SubDir in @(
    "config",
    "data",
    "data\photos",
    "data\photos\captures",
    "data\photos\uploads",
    "data\history",
    "data\database",
    "cache",
    "logs"
)) {
    New-Item -ItemType Directory -Force -Path (Join-Path $FinalBundleRoot $SubDir) | Out-Null
}
if (-not (Test-Path -LiteralPath (Join-Path $FinalBundleRoot "config\app.json"))) {
    Write-DefaultConfigFiles `
        -ConfigDir (Join-Path $FinalBundleRoot "config") `
        -InstallDirValue $FinalBundleRoot `
        -AppVersion $Version
}

if (-not $SkipInstaller) {
    if (-not (Test-Path -LiteralPath $InstallerScriptPath -PathType Leaf)) {
        throw "Inno Setup script not found: $InstallerScriptPath"
    }
    $IsccPath = Find-InnoSetupCompiler
    if (-not $IsccPath) {
        throw "Inno Setup 6 compiler (ISCC.exe) was not found."
    }

    if (Test-Path -LiteralPath $InstallerOutputPath -PathType Leaf) {
        Remove-Item -LiteralPath $InstallerOutputPath -Force
    }

    & $IsccPath `
        "/DMyAppVersion=$Version" `
        "/DSourceDir=$InstallerStagingRoot" `
        $InstallerScriptPath
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup compilation failed."
    }

    if (-not (Test-Path -LiteralPath $InstallerOutputPath -PathType Leaf)) {
        throw "Installer output is missing: $InstallerOutputPath"
    }
}

Remove-SafeTree -Path $StagingRoot -AllowedRoot $BuildRoot
Remove-SafeTree -Path $InstallerStagingRoot -AllowedRoot $BuildRoot
Remove-SafeTree -Path $WorkRoot -AllowedRoot $BuildRoot

$Executable = Get-Item -LiteralPath $FinalExecutablePath
$ExeSizeMb = [Math]::Round($Executable.Length / 1MB, 2)
$ExeHash = (Get-FileHash -LiteralPath $FinalExecutablePath -Algorithm SHA256).Hash

Write-Host "ColorVision version: $Version"
Write-Host "ColorVision bundle: $FinalBundleRoot"
Write-Host "ColorVision EXE: $FinalExecutablePath ($ExeSizeMb MB, SHA-256: $ExeHash)"

if (-not $SkipInstaller) {
    $SetupFile = Get-Item -LiteralPath $InstallerOutputPath
    $SetupSizeMb = [Math]::Round($SetupFile.Length / 1MB, 2)
    $SetupHash = (Get-FileHash -LiteralPath $InstallerOutputPath -Algorithm SHA256).Hash
    Write-Host "ColorVision Setup: $InstallerOutputPath ($SetupSizeMb MB, SHA-256: $SetupHash)"
}
