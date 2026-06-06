@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 > nul
title Sistema de Contratos

cd /d "%~dp0"

set "PS_SCRIPT=%CD%\scripts\start_system.ps1"
set "OUT_FILE=%TEMP%\contratos_start_%RANDOM%%RANDOM%.txt"

echo.
echo Iniciando Sistema de Contratos...
echo.

if not exist "%PS_SCRIPT%" (
    echo ERRO: script nao encontrado:
    echo %PS_SCRIPT%
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo ERRO: ambiente virtual nao encontrado em .venv
    echo.
    echo Abra o PowerShell nesta pasta e execute:
    echo python -m venv .venv
    echo .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" > "%OUT_FILE%" 2>&1
set "START_EXIT=%ERRORLEVEL%"

type "%OUT_FILE%"

if not "%START_EXIT%"=="0" (
    echo.
    echo ERRO: nao foi possivel iniciar o sistema.
    echo Confira as mensagens acima.
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
    echo.
    echo Abrindo navegador: !LOGIN_URL!
    start "" "!LOGIN_URL!"
) else (
    echo.
    echo Sistema iniciado, mas a URL nao foi encontrada na saida.
)

del "%OUT_FILE%" > nul 2>&1

echo.
echo Pronto. Voce pode fechar esta janela; o servidor continua em segundo plano.
echo Para parar o sistema, encerre o processo python.exe pelo Gerenciador de Tarefas.
echo.
pause
