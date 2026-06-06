@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 > nul
title Sistema de Contratos
color 0A

cd /d "%~dp0"

set "PS_SCRIPT=%CD%\scripts\start_system.ps1"
set "OUT_FILE=%TEMP%\contratos_start_%RANDOM%%RANDOM%.txt"

echo.
echo ==========================================
echo    SISTEMA DE GESTAO DE CONTRATOS
echo ==========================================
echo.

if not exist "%PS_SCRIPT%" (
    echo [ERRO] Script de inicializacao nao encontrado:
    echo %PS_SCRIPT%
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado em .venv
    echo.
    echo Abra o PowerShell nesta pasta e execute:
    echo python -m venv .venv
    echo .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [*] Atualizando banco de dados...
".venv\Scripts\python.exe" -m alembic upgrade head
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao atualizar banco de dados.
    pause
    exit /b 1
)
echo [OK] Banco de dados atualizado.

echo [*] Iniciando servidor e aguardando resposta...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" > "%OUT_FILE%" 2>&1
set "START_EXIT=%ERRORLEVEL%"

type "%OUT_FILE%"

if not "%START_EXIT%"=="0" (
    echo.
    echo [ERRO] Nao foi possivel iniciar o sistema.
    del "%OUT_FILE%" > nul 2>&1
    echo.
    pause
    exit /b %START_EXIT%
)

set "LOGIN_URL="
for /f "tokens=1,* delims=:" %%A in ('findstr /B /C:"Login:" "%OUT_FILE%"') do (
    set "LOGIN_URL=%%B"
)

if defined LOGIN_URL (
    if "!LOGIN_URL:~0,1!"==" " set "LOGIN_URL=!LOGIN_URL:~1!"
    set "LOGOUT_URL=!LOGIN_URL:/login=/logout!"
    echo.
    echo [OK] Encerrando sessao anterior e abrindo tela de login.
    start "" "!LOGOUT_URL!"
) else (
    echo.
    echo [AVISO] Sistema iniciado, mas a URL de login nao foi encontrada.
)

del "%OUT_FILE%" > nul 2>&1

echo.
echo Pronto. O servidor continua em segundo plano.
echo.
exit /b 0
