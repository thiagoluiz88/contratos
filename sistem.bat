@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 > nul
title Sistema de Contratos

cd /d "%~dp0"

set "PS_SCRIPT=%CD%\scripts\start_system.ps1"
set "OUT_FILE=%TEMP%\contratos_start_%RANDOM%%RANDOM%.txt"
set "LOGIN_URL=http://127.0.0.1:8007/login"
set "LOGOUT_URL=http://127.0.0.1:8007/logout"

echo.
echo Iniciando Sistema de Contratos...
echo.

if not exist "%PS_SCRIPT%" (
    echo ERRO: script nao encontrado:
    echo %PS_SCRIPT%
    timeout /t 10 > nul
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo ERRO: ambiente virtual nao encontrado em .venv
    timeout /t 15 > nul
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" > "%OUT_FILE%" 2>&1
set "START_EXIT=%ERRORLEVEL%"

if not "%START_EXIT%"=="0" (
    type "%OUT_FILE%"
    echo.
    echo ERRO: nao foi possivel iniciar o sistema.
    del "%OUT_FILE%" > nul 2>&1
    timeout /t 15 > nul
    exit /b %START_EXIT%
)

echo.
echo Aguardando o sistema ficar disponivel...

:WAIT_LOGIN
powershell.exe -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%LOGIN_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"

if errorlevel 1 (
    timeout /t 1 /nobreak > nul
    goto WAIT_LOGIN
)

echo.
echo Abrindo tela de login...
start "" "%LOGOUT_URL%"

del "%OUT_FILE%" > nul 2>&1

exit