#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs the CMS Frontend (Next.js standalone) as a Windows service via NSSM.
#>

$ErrorActionPreference = "Stop"

$ServiceName  = "cms-frontend"
$AppDir       = "C:\CMS"
$StandaloneDir = "$AppDir\frontend\.next\standalone"
$EnvFile      = "$AppDir\.env.production"
$LogDir       = "C:\CMS\logs"

function Write-Info { param([string]$Msg) Write-Host "[INFO]  $Msg" -ForegroundColor Green }

# ── Validate prerequisites ────────────────────────────────────────────────────
if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    throw "NSSM not found. Install via: choco install nssm"
}
if (-not (Test-Path "$StandaloneDir\server.js")) {
    throw "Next.js standalone build not found at $StandaloneDir - run 'npm run build' first"
}

$NodeExe = (Get-Command node).Source

# ── Remove existing service ───────────────────────────────────────────────────
$existing = & nssm status $ServiceName 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Info "Removing existing service '$ServiceName'…"
    & nssm stop   $ServiceName 2>&1 | Out-Null
    & nssm remove $ServiceName confirm 2>&1 | Out-Null
}

# ── Install via NSSM ─────────────────────────────────────────────────────────
Write-Info "Installing service '$ServiceName'…"

& nssm install $ServiceName $NodeExe
& nssm set     $ServiceName AppDirectory  $StandaloneDir
& nssm set     $ServiceName AppParameters "server.js"
& nssm set     $ServiceName DisplayName   "CMS Frontend (Next.js)"
& nssm set     $ServiceName Description   "Case Management System — Next.js standalone server"
& nssm set     $ServiceName Start         SERVICE_AUTO_START
& nssm set     $ServiceName AppStdout     "$LogDir\frontend.log"
& nssm set     $ServiceName AppStderr     "$LogDir\frontend-error.log"
& nssm set     $ServiceName AppRotateFiles 1
& nssm set     $ServiceName AppRotateBytes 10485760  # 10 MB

# ── Environment variables ─────────────────────────────────────────────────────
$baseEnv = "PORT=3000`nHOSTNAME=127.0.0.1`nNODE_ENV=production"
if (Test-Path $EnvFile) {
    $fileEnv = (Get-Content $EnvFile |
        Where-Object { $_ -match "^\s*[^#]\S+=.*" } |
        ForEach-Object { $_.Trim() }) -join "`n"
    & nssm set $ServiceName AppEnvironmentExtra "$baseEnv`n$fileEnv"
} else {
    & nssm set $ServiceName AppEnvironmentExtra $baseEnv
}

# ── Restart policy ────────────────────────────────────────────────────────────
& nssm set $ServiceName AppExit Default Restart
& nssm set $ServiceName AppRestartDelay 5000

# ── Start service ─────────────────────────────────────────────────────────────
Write-Info "Starting '$ServiceName'…"
& nssm start $ServiceName

Start-Sleep -Seconds 3
$status = & nssm status $ServiceName
Write-Info "Service status: $status"
