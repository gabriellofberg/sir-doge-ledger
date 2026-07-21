# SirDoge Ledger — Windows start script
#   .\scripts\run_windows.ps1        Development: backend + Vite (open auth)
#   .\scripts\run_windows.ps1 prod   Build frontend, single port (password auth)
# Compatible with Windows PowerShell 5.1

param(
    [ValidateSet("dev", "prod")]
    [string]$Mode = "dev"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }

function Write-Banner {
    Write-Host "======================================================"
    Write-Host " SirDoge Ledger"
    Write-Host " Local finance & life admin — fancy Doge, no cloud."
    Write-Host "======================================================"
}

function Get-SystemPython {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return $pythonCmd.Source
    }
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        return "PY_LAUNCHER"
    }
    throw "Python not found. Install Python 3.11+ and enable Add to PATH."
}

function New-ProjectVenv {
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }

    Write-Host "Creating Python virtual environment (.venv)..."
    $systemPython = Get-SystemPython
    if ($systemPython -eq "PY_LAUNCHER") {
        & py -3 -m venv (Join-Path $Root ".venv")
    }
    else {
        & $systemPython -m venv (Join-Path $Root ".venv")
    }

    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "Failed to create .venv. Check Python installation."
    }
    return $venvPython
}

function Invoke-Npm {
    param([string[]]$NpmArgs)
    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npmCmd) {
        throw "npm not found. Install Node.js 18+ from https://nodejs.org/"
    }
    & npm @NpmArgs
    if ($LASTEXITCODE -ne 0) {
        throw "npm command failed: npm $($NpmArgs -join ' ')"
    }
}

Write-Banner

$PythonExe = New-ProjectVenv

Write-Host "Installing backend deps..."
& $PythonExe -m pip install -q -r (Join-Path $Root "backend\requirements-dev.txt")
if ($LASTEXITCODE -ne 0) {
    throw "pip install failed."
}

$nodeModules = Join-Path $Root "frontend\node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "Installing frontend deps..."
    Push-Location (Join-Path $Root "frontend")
    try {
        Invoke-Npm -NpmArgs @("install")
    }
    finally {
        Pop-Location
    }
}

$env:PYTHONPATH = "$(Join-Path $Root 'backend')" + $(if ($env:PYTHONPATH) { ";$env:PYTHONPATH" } else { "" })

if ($Mode -eq "prod") {
    Remove-Item Env:SIR_DOGE_DEV -ErrorAction SilentlyContinue
    $env:SIR_DOGE_PROD = "1"
    Write-Host "Building frontend..."
    Push-Location (Join-Path $Root "frontend")
    try {
        Invoke-Npm -NpmArgs @("run", "build")
    }
    finally {
        Pop-Location
    }
    Write-Host "Serving on http://127.0.0.1:${BackendPort}/"
    Write-Host "Set a password on first visit. Recovery key saved to %LOCALAPPDATA%\sir-doge-ledger\recovery-hint.txt"
    & $PythonExe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $BackendPort
    exit $LASTEXITCODE
}

$env:SIR_DOGE_DEV = "1"
Remove-Item Env:SIR_DOGE_PROD -ErrorAction SilentlyContinue
Write-Host "Dev mode: no password required (SIR_DOGE_DEV=1)"
Write-Host "Backend  http://127.0.0.1:${BackendPort}/api/health"
Write-Host "Frontend http://127.0.0.1:${FrontendPort}/"

$backend = Start-Process -FilePath $PythonExe -ArgumentList @(
    "-m", "uvicorn", "app.main:app",
    "--app-dir", "backend",
    "--host", "127.0.0.1",
    "--port", $BackendPort,
    "--reload"
) -PassThru -NoNewWindow

try {
    $healthUrl = "http://127.0.0.1:${BackendPort}/api/health"
    Write-Host "Waiting for backend..."
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $null = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 1
            $ready = $true
            Write-Host "Backend ready."
            break
        }
        catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $ready) {
        throw "Backend did not start on port $BackendPort — check errors above."
    }

    Start-Process "http://127.0.0.1:${FrontendPort}/"

    Push-Location (Join-Path $Root "frontend")
    try {
        Invoke-Npm -NpmArgs @("run", "dev", "--", "--host", "127.0.0.1", "--port", $FrontendPort)
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
}
