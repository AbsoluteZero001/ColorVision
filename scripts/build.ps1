[CmdletBinding()]
param(
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"
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

if ($FrontendOnly) {
    Write-Host "Frontend build completed."
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
