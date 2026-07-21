# SirDoge Ledger - Windows build script
# Requires: Python 3.11+, Node.js, PyInstaller, Inno Setup 6 (optional)
# Compatible with Windows PowerShell 5.1

param(
    [switch]$SkipFrontend,
    [switch]$InstallerOnly
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Write-Banner {
    param([string]$Title)
    Write-Host "======================================================"
    Write-Host " $Title"
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

Write-Banner "SirDoge Ledger - Windows build"

if (-not $InstallerOnly) {
    if (-not $SkipFrontend) {
        Write-Host "Building frontend..."
        Push-Location (Join-Path $Root "frontend")
        try {
            if (-not (Test-Path "node_modules")) {
                Invoke-Npm -NpmArgs @("install")
            }
            Invoke-Npm -NpmArgs @("run", "build")
        }
        finally {
            Pop-Location
        }
    }

    $PythonExe = New-ProjectVenv

    Write-Host "Installing Python dependencies..."
    & $PythonExe -m pip install -q -r (Join-Path $Root "backend\requirements-dev.txt") pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed."
    }

    Write-Host "Running tests..."
    $prevDataDir = $env:SIR_DOGE_DATA_DIR
    $env:SIR_DOGE_DATA_DIR = Join-Path $env:TEMP "sir-doge-build-test"
    try {
        & $PythonExe -m pytest (Join-Path $Root "backend\tests") -q
        if ($LASTEXITCODE -ne 0) {
            throw "pytest failed."
        }
    }
    finally {
        if ($null -eq $prevDataDir) {
            Remove-Item Env:SIR_DOGE_DATA_DIR -ErrorAction SilentlyContinue
        }
        else {
            $env:SIR_DOGE_DATA_DIR = $prevDataDir
        }
    }

    Write-Host "Building PyInstaller bundle..."
    & $PythonExe -m PyInstaller --noconfirm (Join-Path $Root "sir-doge.spec")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }
}

$inno = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
if (Test-Path $inno) {
    Write-Host "Building Inno Setup installer..."
    & $inno (Join-Path $Root "installer\windows\setup.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup build failed."
    }
    Write-Host "Installer: dist\installer\SirDogeLedger-Setup.exe"
}
else {
    Write-Host "Inno Setup not found - portable bundle at dist\SirDogeLedger\"
    Write-Host "Install Inno Setup 6 to create SirDogeLedger-Setup.exe"
    Write-Host "Download: https://jrsoftware.org/isdl.php"
}

Write-Host "Done."
