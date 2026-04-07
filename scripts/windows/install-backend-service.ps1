#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs the CMS Backend as a Windows service via NSSM.
#>

$ErrorActionPreference = "Stop"

$ServiceName = "cms-backend"
$AppDir      = "C:\CMS"
$VenvPython  = "$AppDir\backend\venv\Scripts\python.exe"
$EnvFile     = "$AppDir\.env.production"
$LogDir      = "C:\CMS\logs"

function Write-Info { param([string]$Msg) Write-Host "[INFO]  $Msg" -ForegroundColor Green }

# ── Validate prerequisites ────────────────────────────────────────────────────
if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    throw "NSSM not found. Install via: choco install nssm"
}
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment not found at $VenvPython - run setup.ps1 first"
}

# ── Remove existing service ───────────────────────────────────────────────────
$existing = & nssm status $ServiceName 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Info "Removing existing service '$ServiceName'…"
    & nssm stop   $ServiceName 2>&1 | Out-Null
    & nssm remove $ServiceName confirm 2>&1 | Out-Null
}

# ── Load environment variables for service ────────────────────────────────────
$envVars = @{}
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -match "^\s*[^#]\S+=.*" } | ForEach-Object {
        $parts = $_ -split "=", 2
        $envVars[$parts[0].Trim()] = $parts[1].Trim()
    }
}

$DatabaseUrl = if ($envVars.ContainsKey("DATABASE_URL")) { $envVars["DATABASE_URL"] } else { "postgresql+asyncpg://cms_user:password@localhost:5432/cms_production" }

# ── Install via NSSM ─────────────────────────────────────────────────────────
Write-Info "Installing service '$ServiceName'…"

& nssm install $ServiceName $VenvPython
& nssm set     $ServiceName AppDirectory  "$AppDir\backend"
& nssm set     $ServiceName AppParameters "-m uvicorn backend.src.main:app --host 127.0.0.1 --port 8000 --workers 4"
& nssm set     $ServiceName DisplayName   "CMS Backend (FastAPI)"
& nssm set     $ServiceName Description   "Case Management System — FastAPI/Uvicorn backend"
& nssm set     $ServiceName Start         SERVICE_AUTO_START
& nssm set     $ServiceName AppStdout     "$LogDir\backend.log"
& nssm set     $ServiceName AppStderr     "$LogDir\backend-error.log"
& nssm set     $ServiceName AppRotateFiles 1
& nssm set     $ServiceName AppRotateBytes 10485760  # 10 MB

# ── Environment variables ─────────────────────────────────────────────────────
if (Test-Path $EnvFile) {
    $envString = (Get-Content $EnvFile |
        Where-Object { $_ -match "^\s*[^#]\S+=.*" } |
        ForEach-Object { $_.Trim() }) -join "`n"
    & nssm set $ServiceName AppEnvironmentExtra $envString
}

# ── Restart policy ────────────────────────────────────────────────────────────
& nssm set $ServiceName AppExit Default Restart
& nssm set $ServiceName AppRestartDelay 5000

# ── Start service ─────────────────────────────────────────────────────────────
Write-Info "Starting '$ServiceName'…"
& nssm start $ServiceName

Start-Sleep -Seconds 2
$status = & nssm status $ServiceName
Write-Info "Service status: $status"
