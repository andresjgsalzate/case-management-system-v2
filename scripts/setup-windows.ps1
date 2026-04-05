# ============================================================
# Case Management System — Windows setup script (PowerShell)
# Verifies prerequisites, creates venv, and installs dependencies
# ============================================================

param()
$ErrorActionPreference = "Stop"

function Write-Info  { param($msg) Write-Host "[INFO]  $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# ─── Check prerequisites ─────────────────────────────────────────────────────

Write-Info "Checking prerequisites..."

# Python 3.11+
try {
    $pythonVersion = python --version 2>&1
    $version = ($pythonVersion -replace "Python ", "").Trim()
    $parts = $version.Split(".")
    if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 11)) {
        Write-Err "Python 3.11+ required. Found: $version"
    }
    Write-Info "Python $version ✓"
} catch {
    Write-Err "Python is not installed. Install Python 3.11+ from https://python.org"
}

# Node.js 18+
try {
    $nodeVersion = node --version 2>&1
    $nodeMajor = [int](($nodeVersion -replace "v", "").Split(".")[0])
    if ($nodeMajor -lt 18) {
        Write-Err "Node.js 18+ required. Found: $nodeVersion"
    }
    Write-Info "Node.js $nodeVersion ✓"
} catch {
    Write-Err "Node.js is not installed. Install Node.js 18+ from https://nodejs.org"
}

# npm
try {
    $npmVersion = npm --version 2>&1
    Write-Info "npm $npmVersion ✓"
} catch {
    Write-Err "npm is not installed."
}

# ─── Backend setup ────────────────────────────────────────────────────────────

Write-Info "Setting up backend..."

Set-Location "$ProjectRoot\backend"

if (-not (Test-Path "venv")) {
    Write-Info "Creating virtual environment..."
    python -m venv venv
}

Write-Info "Installing backend dependencies..."
& "venv\Scripts\pip.exe" install --upgrade pip --quiet
& "venv\Scripts\pip.exe" install -r requirements-dev.txt --quiet
Write-Info "Backend dependencies installed ✓"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Warn ".env created from .env.example — update DATABASE_URL and SECRET_KEY"
}

# ─── Frontend setup ───────────────────────────────────────────────────────────

Write-Info "Setting up frontend..."

Set-Location "$ProjectRoot\frontend"

Write-Info "Installing Node.js dependencies..."
npm ci --silent
Write-Info "Frontend dependencies installed ✓"

if (-not (Test-Path ".env.local")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env.local"
    } else {
        Write-Warn ".env.example not found in frontend/"
    }
}

# ─── Done ─────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Info "Setup complete! Next steps:"
Write-Host "  1. Edit backend\.env — set DATABASE_URL and SECRET_KEY"
Write-Host "  2. Run migrations: cd backend; .\venv\Scripts\activate; alembic upgrade head"
Write-Host "  3. Start backend: cd backend; uvicorn src.main:app --reload"
Write-Host "  4. Start frontend: cd frontend; npm run dev"
