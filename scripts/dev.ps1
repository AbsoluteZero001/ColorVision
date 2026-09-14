[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FrontendRoot = Join-Path $ProjectRoot "frontend"

if ($BackendOnly -and $FrontendOnly) {
    throw "Use either -BackendOnly or -FrontendOnly, not both."
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment not found. Create .venv and install requirements first."
}

if (-not $FrontendOnly -and -not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) {
    throw "Frontend dependencies not found. Run npm install in the frontend directory first."
}

$BackendArguments = @(
    "-m",
    "uvicorn",
    "backend.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8000"
)

if ($BackendOnly) {
    & $Python @BackendArguments --reload
    exit $LASTEXITCODE
}

Push-Location $FrontendRoot
try {
    if ($FrontendOnly) {
        npm run dev
        exit $LASTEXITCODE
    }

    Write-Host "Starting ColorVision backend at http://127.0.0.1:8000"
    $BackendProcess = Start-Process `
        -FilePath $Python `
        -ArgumentList $BackendArguments `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -PassThru

    try {
        Write-Host "Starting ColorVision frontend at http://127.0.0.1:5173"
        npm run dev
    }
    finally {
        if ($BackendProcess -and -not $BackendProcess.HasExited) {
            Stop-Process -Id $BackendProcess.Id
        }
    }
}
finally {
    Pop-Location
}
