@echo off
chcp 65001 > nul
color 0A

setlocal enabledelayedexpansion

cd /d "%~dp0.."

echo.
echo ╔══════════════════════════════════════════╗
echo ║   SISTEMA DE GESTAO DE CONTRATOS        ║
echo ╚══════════════════════════════════════════╝
echo.

REM Verificar .venv
if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual nao encontrado em .venv
    pause
    exit /b 1
)

REM Ativar venv
call .venv\Scripts\activate.bat

REM Liberar porta 8000
echo [*] Verificando porta 8000...
for /f "tokens=5" %%A in ('netstat -ano 2^>nul ^| find ":8000 "') do (
    echo [!] Matando processo anterior (PID %%A)...
    taskkill /PID %%A /F >nul 2>&1
    timeout /t 1 >nul
)

REM Atualizar banco
echo [*] Atualizando banco de dados...
python -m alembic upgrade head >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Falha ao atualizar banco de dados
    pause
    exit /b 1
)
echo [OK] Banco de dados atualizado

REM Iniciar servidor em background
echo [*] Iniciando servidor em background...
start "Contratos Server" python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

REM Aguardar servidor ficar pronto
echo [*] Aguardando servidor responder...
setlocal enabledelayedexpansion
set "counter=0"
:check_server
timeout /t 1 >nul
set /a counter=!counter!+1

if !counter! geq 15 (
    echo [ERRO] Servidor nao respondeu em 15 segundos
    pause
    exit /b 1
)

REM Testar se servidor esta respondendo
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop; exit 0 } catch { exit 1 }"
if errorlevel 1 goto check_server

echo [OK] Servidor respondendo!
echo [*] Abrindo navegador...

REM Abrir URL
explorer.exe "http://127.0.0.1:8000/login"

echo [OK] Sistema iniciado com sucesso!
echo [*] Para parar o servidor, feche a janela do terminal
echo.

pause
