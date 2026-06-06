@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo [DEBUG] Diretorio atual: %cd%
echo [DEBUG] Verificando .venv...

if exist ".venv\Scripts\python.exe" (
    echo [OK] .venv encontrado
) else (
    echo [ERRO] .venv NAO encontrado
    pause
    exit /b 1
)

echo.
echo [DEBUG] Ativando venv...
call .venv\Scripts\activate.bat

if errorlevel 1 (
    echo [ERRO] Falha ao ativar venv
    pause
    exit /b 1
)

echo [OK] Venv ativado

echo.
echo [DEBUG] Atualizando banco de dados...
python -m alembic upgrade head

if errorlevel 1 (
    echo [ERRO] Falha ao atualizar banco
    pause
    exit /b 1
)

echo [OK] Banco atualizado

echo.
echo [DEBUG] Iniciando servidor...
echo. 
echo Para parar, pressione Ctrl+C
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
