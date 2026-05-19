# dev.ps1 — Entry-point PowerShell para arrancar el sistema completo.
# Replica dev.bat: localiza Git Bash, asegura Docker Desktop arriba,
# y delega a dev.sh con los args originales.
#
# Uso:
#   .\dev.ps1
#   .\dev.ps1 --fresh
#
# Si PowerShell bloquea el script:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "Sistema de Gestion de Casos - Dev"

Write-Host ""
Write-Host " ==========================================" -ForegroundColor Cyan
Write-Host "  Sistema de Gestion de Casos" -ForegroundColor Cyan
Write-Host " ==========================================" -ForegroundColor Cyan
Write-Host ""

# ── Localizar Git Bash ───────────────────────────────────────
$bashCandidates = @(
    "C:\Program Files\Git\bin\bash.exe",
    "C:\Program Files (x86)\Git\bin\bash.exe"
)

$bash = $null
foreach ($candidate in $bashCandidates) {
    if (Test-Path $candidate) {
        $bash = $candidate
        break
    }
}

# Fallback: where.exe excluyendo System32 (WSL bash) y sysnative.
if (-not $bash) {
    $whereOut = & where.exe bash 2>$null
    if ($LASTEXITCODE -eq 0 -and $whereOut) {
        foreach ($line in $whereOut) {
            if ($line -notmatch "System32|sysnative|wsl") {
                $bash = $line.Trim()
                break
            }
        }
    }
}

if (-not $bash) {
    Write-Host " [ERROR] Git Bash no encontrado." -ForegroundColor Red
    Write-Host "         Instala Git for Windows: https://git-scm.com/download/win" -ForegroundColor Red
    Write-Host "         O ejecuta directamente desde Git Bash: bash dev.sh" -ForegroundColor Red
    Write-Host ""
    Read-Host "Presiona Enter para cerrar"
    exit 1
}

Write-Host " Usando bash: $bash" -ForegroundColor Green
Write-Host ""

# ── Verificar Docker Desktop ─────────────────────────────────
Write-Host " Verificando Docker Desktop..." -ForegroundColor Yellow
& docker info 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host " [Docker] Docker ya esta corriendo" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host " [Docker] El daemon no esta corriendo. Buscando Docker Desktop..." -ForegroundColor Yellow

    $dockerAppCandidates = @(
        "C:\Program Files\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    )

    $dockerApp = $null
    foreach ($candidate in $dockerAppCandidates) {
        if (Test-Path $candidate) {
            $dockerApp = $candidate
            break
        }
    }

    if (-not $dockerApp) {
        Write-Host " [ERROR] Docker Desktop no encontrado en rutas comunes." -ForegroundColor Red
        Write-Host "         Abrelo manualmente y vuelve a ejecutar este script." -ForegroundColor Red
        Write-Host ""
        Read-Host "Presiona Enter para cerrar"
        exit 1
    }

    Write-Host " [Docker] Abriendo Docker Desktop..." -ForegroundColor Yellow
    Start-Process -FilePath $dockerApp

    Write-Host " [Docker] Esperando que el daemon este listo (hasta 90 seg)..." -ForegroundColor Yellow

    $attempts = 0
    $maxAttempts = 30
    $ready = $false

    while ($attempts -lt $maxAttempts) {
        Start-Sleep -Seconds 3
        $attempts++
        & docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
    }

    if (-not $ready) {
        Write-Host " [ERROR] Docker no respondio despues de 90 segundos." -ForegroundColor Red
        Write-Host "         Verifica que Docker Desktop este instalado correctamente." -ForegroundColor Red
        Write-Host ""
        Read-Host "Presiona Enter para cerrar"
        exit 1
    }

    Write-Host " [Docker] Docker listo" -ForegroundColor Green
    Write-Host ""
}

# ── Ejecutar dev.sh con Git Bash ─────────────────────────────
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$devSh = Join-Path $scriptDir "dev.sh"

if (-not (Test-Path $devSh)) {
    Write-Host " [ERROR] dev.sh no encontrado en: $devSh" -ForegroundColor Red
    Write-Host ""
    Read-Host "Presiona Enter para cerrar"
    exit 1
}

# Forwarding de args. Git Bash necesita rutas tipo Unix; convertimos a posix path.
$devShPosix = $devSh -replace '\\', '/' -replace '^([A-Za-z]):', '/$1'

& $bash $devShPosix @args
$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -ne 0) {
    Write-Host " [ERROR] El script termino con codigo: $exitCode" -ForegroundColor Red
    Write-Host "         Revisa los mensajes de arriba." -ForegroundColor Red
} else {
    Write-Host " [OK] Script finalizado correctamente." -ForegroundColor Green
}

Write-Host ""
Read-Host "Presiona Enter para cerrar esta ventana"
exit $exitCode
