#Requires -RunAsAdministrator
<#
.SYNOPSIS
    CMS Windows Server Setup — installs all dependencies and configures the application.
.DESCRIPTION
    Uses Chocolatey to install: Python 3.11, Node.js 20, PostgreSQL 15, Redis, NSSM.
    Creates the database, builds the frontend, and runs migrations.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup.ps1
#>

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# ── Configuration ─────────────────────────────────────────────────────────────
$AppDir   = "C:\CMS"
$DataDir  = "C:\CMS\data"
$LogDir   = "C:\CMS\logs"
$DbName   = "cms_production"
$DbUser   = "cms_user"
$NodeVer  = "20"
$PyVer    = "3.11"

function Write-Info  { param([string]$Msg) Write-Host "[INFO]  $Msg" -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Host "[WARN]  $Msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$Msg) Write-Host "[ERROR] $Msg" -ForegroundColor Red; exit 1 }

# ── Chocolatey ────────────────────────────────────────────────────────────────
Write-Info "Checking Chocolatey…"
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Info "Installing Chocolatey…"
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    $env:PATH += ";$env:ALLUSERSPROFILE\chocolatey\bin"
}
Write-Info "Chocolatey $(choco --version)"

# ── Install packages ──────────────────────────────────────────────────────────
$packages = @(
    "python --version=$PyVer",
    "nodejs --version=$NodeVer",
    "postgresql15",
    "redis-64",
    "nssm",
    "git"
)

foreach ($pkg in $packages) {
    Write-Info "Installing $pkg…"
    choco install $pkg -y --no-progress 2>&1 | Out-Null
}

# Refresh PATH after installs
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH", "User")

# ── Directory structure ───────────────────────────────────────────────────────
Write-Info "Creating directories…"
@($AppDir, "$AppDir\backend", "$AppDir\frontend", $DataDir, $LogDir,
  "$DataDir\uploads", "$DataDir\backups") | ForEach-Object {
    New-Item -ItemType Directory -Force -Path $_ | Out-Null
}

# ── PostgreSQL setup ──────────────────────────────────────────────────────────
Write-Info "Configuring PostgreSQL…"
$PgBin   = (Get-ChildItem "C:\Program Files\PostgreSQL" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName + "\bin"
$env:PATH += ";$PgBin"

$DbPass = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 24 | ForEach-Object { [char]$_ })

$pgCommands = @(
    "CREATE USER $DbUser WITH PASSWORD '$DbPass';",
    "CREATE DATABASE $DbName OWNER $DbUser;",
    "GRANT ALL PRIVILEGES ON DATABASE $DbName TO $DbUser;"
)

foreach ($cmd in $pgCommands) {
    & "$PgBin\psql" -U postgres -c $cmd 2>&1 | Out-Null
}

Write-Info "PostgreSQL credentials:"
Write-Info "  DB_USER = $DbUser"
Write-Info "  DB_PASS = $DbPass   ← save this!"
Write-Info "  DB_NAME = $DbName"

# ── Redis as Windows Service ──────────────────────────────────────────────────
Write-Info "Starting Redis service…"
Start-Service "Redis" -ErrorAction SilentlyContinue
Set-Service  "Redis" -StartupType Automatic -ErrorAction SilentlyContinue

# ── Python virtual environment ────────────────────────────────────────────────
Write-Info "Creating Python virtual environment…"
$VenvDir = "$AppDir\backend\venv"
& python -m venv $VenvDir
& "$VenvDir\Scripts\pip" install --quiet --upgrade pip wheel

$RepoDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (Test-Path "$RepoDir\backend\requirements.txt") {
    Write-Info "Installing Python dependencies…"
    & "$VenvDir\Scripts\pip" install --quiet -r "$RepoDir\backend\requirements.txt"
} else {
    Write-Warn "requirements.txt not found - skipping"
}

# ── Copy application files ────────────────────────────────────────────────────
Write-Info "Copying application to $AppDir…"

# Backend
$robocopyArgs = @("$RepoDir\backend", "$AppDir\backend", "/E", "/XD", "__pycache__", ".git", "venv", "/XF", "*.pyc")
& robocopy @robocopyArgs | Out-Null

# Frontend
$robocopyArgs = @("$RepoDir\frontend", "$AppDir\frontend", "/E", "/XD", "node_modules", ".git", "/XF", ".env*")
& robocopy @robocopyArgs | Out-Null

# ── Frontend build ────────────────────────────────────────────────────────────
Write-Info "Building Next.js frontend…"
Push-Location "$AppDir\frontend"
& npm ci --silent
& npm run build
Pop-Location

# ── .env.production ───────────────────────────────────────────────────────────
$EnvFile = "$AppDir\.env.production"
if (-not (Test-Path $EnvFile)) {
    Write-Info "Creating .env.production template…"
    Copy-Item "$RepoDir\scripts\shared\.env.production.example" $EnvFile
    $Secret = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    (Get-Content $EnvFile) `
        -replace "cms_user:CHANGE_ME@", "cms_user:$DbPass@" `
        -replace "CHANGE_ME_use_openssl_rand_hex_32", $Secret |
        Set-Content $EnvFile
    Write-Warn "Edit $EnvFile to set SMTP, domain, and other values"
}

# ── Database migrations ───────────────────────────────────────────────────────
Write-Info "Running Alembic migrations…"
Push-Location "$AppDir\backend"
try {
    & "$VenvDir\Scripts\alembic" upgrade head
} catch {
    Write-Warn "Migrations failed - run manually after configuring .env.production"
}
Pop-Location

# ── Install NSSM services ─────────────────────────────────────────────────────
Write-Info "Installing CMS services…"
& "$PSScriptRoot\install-backend-service.ps1"
& "$PSScriptRoot\install-frontend-service.ps1"

# ── IIS / URL Rewrite (optional) ─────────────────────────────────────────────
if (Get-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole | Where-Object { $_.State -eq "Enabled" }) {
    Write-Info "IIS detected - copying web.config..."
    Copy-Item "$PSScriptRoot\web.config" "$AppDir\frontend\"
} else {
    Write-Warn "IIS not enabled - skipping web.config copy"
}

Write-Info ""
Write-Info "Setup complete!"
Write-Info "  1. Edit $EnvFile with your real SMTP / domain values"
Write-Info "  2. Configure IIS ARR or another reverse proxy for HTTPS"
Write-Info "  3. Restart services: nssm restart cms-backend; nssm restart cms-frontend"
