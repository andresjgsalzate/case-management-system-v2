@echo off
title Sistema de Gestion de Casos — Dev
cls

echo.
echo  ==========================================
echo   Sistema de Gestion de Casos
echo  ==========================================
echo.

:: Buscar Git Bash en ubicaciones comunes
set "BASH="
if exist "C:\Program Files\Git\bin\bash.exe"      set "BASH=C:\Program Files\Git\bin\bash.exe"
if exist "C:\Program Files (x86)\Git\bin\bash.exe" set "BASH=C:\Program Files (x86)\Git\bin\bash.exe"

:: Intentar detectarlo via 'where' excluyendo WSL/System32
if "%BASH%"=="" (
    for /f "tokens=*" %%i in ('where bash 2^>nul') do (
        echo %%i | findstr /i "System32\|sysnative\|wsl" >nul 2>&1
        if errorlevel 1 (
            if "%BASH%"=="" set "BASH=%%i"
        )
    )
)

if "%BASH%"=="" (
    echo [ERROR] Git Bash no encontrado.
    echo         Instala Git for Windows: https://git-scm.com/download/win
    echo         O abre este script desde Git Bash directamente con: bash dev.sh
    echo.
    pause
    exit /b 1
)

echo  Usando bash: %BASH%
echo.

:: ── Verificar y arrancar Docker Desktop si no está corriendo ──
echo  Verificando Docker Desktop...
docker info >nul 2>&1
if not errorlevel 1 goto DOCKER_ALREADY_RUNNING

echo  [Docker] El daemon no esta corriendo. Buscando Docker Desktop...
set "DOCKER_APP="
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" set "DOCKER_APP=C:\Program Files\Docker\Docker\Docker Desktop.exe"
if exist "%LOCALAPPDATA%\Docker\Docker Desktop.exe"           set "DOCKER_APP=%LOCALAPPDATA%\Docker\Docker Desktop.exe"

if "%DOCKER_APP%"=="" (
    echo  [ERROR] Docker Desktop no encontrado en las rutas comunes.
    echo          Abrelo manualmente y vuelve a ejecutar este script.
    echo.
    pause
    exit /b 1
)

echo  [Docker] Abriendo Docker Desktop...
start "" "%DOCKER_APP%"
echo  [Docker] Esperando que el daemon este listo (hasta 90 seg)...
set /a INTENTOS=0

:WAIT_DOCKER
timeout /t 3 /nobreak >nul
set /a INTENTOS+=1
docker info >nul 2>&1
if not errorlevel 1 goto DOCKER_OK
if %INTENTOS% geq 30 (
    echo  [ERROR] Docker no respondio despues de 90 segundos.
    echo          Verifica que Docker Desktop este instalado correctamente.
    echo.
    pause
    exit /b 1
)
goto WAIT_DOCKER

:DOCKER_OK
echo  [Docker] Docker listo
echo.
goto DOCKER_DONE

:DOCKER_ALREADY_RUNNING
echo  [Docker] Docker ya esta corriendo
echo.

:DOCKER_DONE

:: Ejecutar el script con Git Bash
"%BASH%" "%~dp0dev.sh" %*

:: Guardar el codigo de salida
set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE% neq 0 (
    echo  [ERROR] El script termino con codigo de error: %EXIT_CODE%
    echo          Revisa los mensajes de arriba para ver que fallo.
) else (
    echo  [OK] Script finalizado correctamente.
)

echo.
echo  Presiona cualquier tecla para cerrar esta ventana...
pause >nul
exit /b %EXIT_CODE%
