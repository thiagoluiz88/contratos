@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 > nul
title Atualizar Banco e GitHub

cd /d "%~dp0"

set "PYTHON=%CD%\.venv\Scripts\python.exe"
set "BACKUP_SCRIPT=%CD%\scripts\backup_database.bat"

echo.
echo ==========================================
echo    ATUALIZAR BANCO E GITHUB
echo ==========================================
echo.

if not exist "%PYTHON%" (
    echo [ERRO] Ambiente virtual nao encontrado em .venv
    goto :ERROR
)

if not exist "%BACKUP_SCRIPT%" (
    echo [ERRO] Script de backup nao encontrado:
    echo %BACKUP_SCRIPT%
    goto :ERROR
)

where git > nul 2>&1
if errorlevel 1 (
    echo [ERRO] Git nao encontrado no computador.
    goto :ERROR
)

git rev-parse --is-inside-work-tree > nul 2>&1
if errorlevel 1 (
    echo [ERRO] Esta pasta nao e um repositorio Git.
    goto :ERROR
)

echo [1/5] Gerando backup local dos cadastros...
call "%BACKUP_SCRIPT%"
if errorlevel 1 (
    echo.
    echo [ERRO] O backup dos cadastros falhou. Nada foi enviado ao GitHub.
    goto :ERROR
)
echo [OK] Backup salvo na pasta backups.
echo.

echo [2/5] Aplicando atualizacoes do banco de dados...
"%PYTHON%" -m alembic upgrade head
if errorlevel 1 (
    echo.
    echo [ERRO] A atualizacao do banco falhou. Nada foi enviado ao GitHub.
    goto :ERROR
)
echo [OK] Banco de dados atualizado.
echo.

echo [3/5] Alteracoes encontradas:
git status --short
echo.

set "HAS_CHANGES="
for /f "delims=" %%A in ('git status --porcelain') do set "HAS_CHANGES=1"

if not defined HAS_CHANGES (
    echo [OK] Nao existem alteracoes de codigo para enviar ao GitHub.
    goto :SUCCESS
)

echo O backup dos cadastros NAO sera enviado ao GitHub.
echo Somente os arquivos exibidos acima e permitidos pelo .gitignore serao enviados.
echo.
set /p "CONFIRM=Digite ENVIAR para criar o commit e atualizar o GitHub: "
if /I not "!CONFIRM!"=="ENVIAR" (
    echo.
    echo Operacao cancelada. O backup local foi mantido.
    goto :SUCCESS
)

echo.
echo [4/5] Criando commit...
call :CLEAR_GIT_LOCK
if errorlevel 1 goto :ERROR

git add -A
if errorlevel 1 (
    echo [ERRO] Nao foi possivel preparar as alteracoes.
    goto :ERROR
)

git diff --cached --quiet
if not errorlevel 1 (
    echo [OK] Nenhuma alteracao permitida para registrar.
    goto :SUCCESS
)

for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set "STAMP=%%I"
git commit -m "Atualizacao do sistema !STAMP!"
if errorlevel 1 (
    echo [ERRO] Nao foi possivel criar o commit.
    goto :ERROR
)

for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if not defined BRANCH (
    echo [ERRO] Nao foi possivel identificar a branch atual.
    goto :ERROR
)

echo.
echo [5/5] Enviando branch !BRANCH! ao GitHub...
git push -u origin "!BRANCH!"
if errorlevel 1 (
    echo.
    echo [ERRO] O commit foi criado localmente, mas o envio ao GitHub falhou.
    echo Verifique sua internet, autenticacao ou se existem alteracoes remotas.
    goto :ERROR
)

echo [OK] GitHub atualizado com sucesso.

:SUCCESS
echo.
echo Processo concluido.
timeout /t 5 > nul
exit /b 0

:ERROR
echo.
echo Processo interrompido. Revise a mensagem acima.
pause
exit /b 1

:CLEAR_GIT_LOCK
if not exist ".git\index.lock" exit /b 0

tasklist /FI "IMAGENAME eq git.exe" 2>nul | find /I "git.exe" >nul
if not errorlevel 1 (
    echo [ERRO] Existe uma operacao Git em andamento.
    echo Feche o Git ou aguarde a operacao terminar e tente novamente.
    exit /b 1
)

echo [AVISO] Removendo trava antiga do Git...
del /F /Q ".git\index.lock" >nul 2>&1
if exist ".git\index.lock" (
    echo [ERRO] Nao foi possivel remover .git\index.lock.
    exit /b 1
)

echo [OK] Trava antiga removida.
exit /b 0
