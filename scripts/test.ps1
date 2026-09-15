[CmdletBinding()]
param(
    [switch]$SkipCamera,
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment not found."
}

if ($SkipCamera) {
    Remove-Item Env:COLORVISION_TEST_CAMERA -ErrorAction SilentlyContinue
}
else {
    $env:COLORVISION_TEST_CAMERA = "1"
}

Push-Location $ProjectRoot
try {
    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) {
        throw "Automated tests failed."
    }
}
finally {
    Pop-Location
}

if (-not $SkipFrontendBuild) {
    $FrontendRoot = Join-Path $ProjectRoot "frontend"
    Push-Location $FrontendRoot
    try {
        npm test
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend workflow tests failed."
        }
        npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend production build failed."
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host "Color recognition system tests completed."
