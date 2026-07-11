@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 > nul
title Atualizar Banco e GitHub com Seguranca

cd /d "%~dp0"

set "PROJECT_DIR=%CD%"
set "PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"
set "BACKUP_SCRIPT=%PROJECT_DIR%\scripts\backup_database.bat"
set "REMOTE=origin"
set "BRANCH="
set "HAS_CHANGES="

echo.
echo ==========================================
echo    ATUALIZAR BANCO E GITHUB COM SEGURANCA
echo ==========================================
echo.
echo Pasta do projeto: %PROJECT_DIR%
echo.

call :CLEAR_GIT_LOCK
if errorlevel 1 goto :ERROR

call :CHECK_PREREQUISITES
if errorlevel 1 goto :ERROR

for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if not defined BRANCH (
    echo [ERRO] Nao foi possivel identificar a branch atual.
    goto :ERROR
)

echo Branch atual: !BRANCH!
echo.

call :CHECK_GIT_OPERATION
if errorlevel 1 goto :ERROR

call :CHECK_SENSITIVE_FILES_IGNORED
if errorlevel 1 goto :ERROR

echo [1/9] Verificando alteracoes locais antes da sincronizacao...
call :SET_HAS_CHANGES

if defined HAS_CHANGES (
    echo.
    echo [AVISO] Existem alteracoes locais ainda nao commitadas:
    git status --short
    echo.
    echo Por seguranca, o GitHub NAO sera baixado agora.
    echo Primeiro revise, teste e publique as alteracoes locais.
) else (
    echo [OK] Arvore de trabalho limpa.
    echo.
    echo [2/9] Baixando atualizacoes do GitHub...
    call :CLEAR_GIT_LOCK
    if errorlevel 1 goto :ERROR
    git fetch "%REMOTE%"
    if errorlevel 1 (
        echo [ERRO] Nao foi possivel consultar o GitHub.
        goto :ERROR
    )

    git pull --ff-only "%REMOTE%" "!BRANCH!"
    if errorlevel 1 (
        echo.
        echo [ERRO] Nao foi possivel atualizar usando fast-forward.
        echo O script nao inicia rebase nem merge automatico.
        echo Revise a divergencia manualmente antes de continuar.
        goto :ERROR
    )
    echo [OK] Codigo local sincronizado com o GitHub.
)

echo.
echo [3/9] Gerando backup local dos cadastros...
call "%BACKUP_SCRIPT%"
if errorlevel 1 (
    echo.
    echo [ERRO] O backup dos cadastros falhou. Nada sera publicado.
    goto :ERROR
)
echo [OK] Backup salvo na pasta backups.

echo.
echo [4/9] Aplicando e validando migrations...
"%PYTHON%" -m alembic upgrade head
if errorlevel 1 goto :TEST_ERROR
"%PYTHON%" -m alembic check
if errorlevel 1 goto :TEST_ERROR
echo [OK] Banco de dados e migrations validados.

echo.
echo [5/9] Executando testes de seguranca e persistencia...
"%PYTHON%" -m scripts.audit_security
if errorlevel 1 goto :TEST_ERROR
"%PYTHON%" -m scripts.audit_persistence
if errorlevel 1 goto :TEST_ERROR
"%PYTHON%" -m app.db_checks
if errorlevel 1 goto :TEST_ERROR
echo [OK] Testes locais aprovados.

echo.
echo [6/9] Verificando vulnerabilidades conhecidas nas dependencias...
"%PYTHON%" -m pip_audit --local
if errorlevel 1 (
    echo.
    echo [ERRO] O pip-audit encontrou vulnerabilidades ou nao conseguiu concluir.
    goto :ERROR
)
echo [OK] Dependencias auditadas.

echo.
echo [7/9] Alteracoes locais encontradas:
git status --short
echo.

call :SET_HAS_CHANGES
if not defined HAS_CHANGES (
    echo [OK] Nao existem alteracoes locais para criar commit.
    goto :CHECK_PUSH_ONLY
)

echo O backup dos cadastros NAO sera enviado ao GitHub.
echo Arquivos locais e sensiveis serao bloqueados antes do commit.
echo.
set /p "CONFIRM_COMMIT=Digite COMMITAR para revisar o staging e criar o commit: "
if /I not "!CONFIRM_COMMIT!"=="COMMITAR" (
    echo.
    echo Operacao encerrada sem criar commit.
    goto :SUCCESS
)

echo.
echo [8/9] Preparando e revisando o commit...
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
    goto :CHECK_PUSH_ONLY
)

call :CHECK_STAGED_SENSITIVE_FILES
if errorlevel 1 goto :UNSTAGE_ERROR

call :CHECK_STAGED_SECRETS
if errorlevel 1 goto :UNSTAGE_ERROR

git diff --cached --check
if errorlevel 1 (
    echo [ERRO] O staging contem problemas de formatacao.
    goto :UNSTAGE_ERROR
)

echo.
echo Arquivos que entrarao no commit:
git diff --cached --name-status
echo.
set /p "FINAL_COMMIT=Digite CONFIRMAR para criar o commit acima: "
if /I not "!FINAL_COMMIT!"=="CONFIRMAR" (
    echo.
    echo Commit cancelado. Os arquivos continuarao no staging para revisao.
    goto :SUCCESS
)

for /f %%I in ('powershell.exe -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm"') do set "STAMP=%%I"
git commit -m "Atualizacao do sistema !STAMP!"
if errorlevel 1 (
    echo [ERRO] Nao foi possivel criar o commit.
    goto :ERROR
)
echo [OK] Commit local criado.

:CHECK_PUSH_ONLY
echo.
echo Atualizando referencia remota antes de verificar o push...
call :CLEAR_GIT_LOCK
if errorlevel 1 goto :ERROR
git fetch "%REMOTE%"
if errorlevel 1 (
    echo [ERRO] Nao foi possivel consultar o GitHub antes do push.
    goto :ERROR
)

git show-ref --verify --quiet "refs/remotes/%REMOTE%/!BRANCH!"
if not errorlevel 1 (
    git merge-base --is-ancestor "%REMOTE%/!BRANCH!" HEAD
    if errorlevel 1 (
        echo.
        echo [ERRO] O GitHub possui commits que ainda nao existem localmente.
        echo O push foi bloqueado. Sincronize a branch manualmente e execute novamente.
        goto :ERROR
    )
)

set "AHEAD_COUNT=0"
for /f %%A in ('git rev-list --count "%REMOTE%/!BRANCH!..HEAD" 2^>nul') do set "AHEAD_COUNT=%%A"

if "!AHEAD_COUNT!"=="0" (
    echo [OK] Nao existem commits locais pendentes de envio.
    goto :SUCCESS
)

echo [9/9] Existem !AHEAD_COUNT! commit(s) local(is) pendente(s) de envio.
git log --oneline "%REMOTE%/!BRANCH!..HEAD"
echo.
set /p "CONFIRM_PUSH=Digite PUBLICAR para enviar esses commits ao GitHub: "
if /I not "!CONFIRM_PUSH!"=="PUBLICAR" (
    echo.
    echo Push cancelado. Os commits permanecem somente neste computador.
    goto :SUCCESS
)

git push -u "%REMOTE%" "!BRANCH!"
if errorlevel 1 (
    echo.
    echo [ERRO] O envio ao GitHub falhou.
    echo O commit local foi preservado. Verifique conexao, autenticacao ou divergencias remotas.
    goto :ERROR
)

echo [OK] GitHub atualizado com sucesso.
goto :SUCCESS

:CHECK_PREREQUISITES
if not exist "%PYTHON%" (
    echo [ERRO] Ambiente virtual nao encontrado:
    echo %PYTHON%
    exit /b 1
)
if not exist "%BACKUP_SCRIPT%" (
    echo [ERRO] Script de backup nao encontrado:
    echo %BACKUP_SCRIPT%
    exit /b 1
)
if not exist "scripts\audit_security.py" (
    echo [ERRO] Auditoria de seguranca nao encontrada.
    exit /b 1
)
if not exist "scripts\audit_persistence.py" (
    echo [ERRO] Auditoria de persistencia nao encontrada.
    exit /b 1
)
where git > nul 2>&1
if errorlevel 1 (
    echo [ERRO] Git nao encontrado no computador.
    exit /b 1
)
git rev-parse --is-inside-work-tree > nul 2>&1
if errorlevel 1 (
    echo [ERRO] Esta pasta nao e um repositorio Git.
    exit /b 1
)
git remote get-url "%REMOTE%" > nul 2>&1
if errorlevel 1 (
    echo [ERRO] Remote "%REMOTE%" nao encontrado.
    exit /b 1
)
"%PYTHON%" -m pip_audit --version > nul 2>&1
if errorlevel 1 (
    echo [ERRO] pip-audit nao esta instalado no ambiente virtual.
    echo Execute: .\.venv\Scripts\python.exe -m pip install pip-audit
    exit /b 1
)
exit /b 0

:CHECK_GIT_OPERATION
for %%D in (rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD) do (
    if exist ".git\%%D" (
        echo [ERRO] Existe uma operacao Git incompleta: %%D
        echo Conclua ou cancele a operacao manualmente antes de continuar.
        exit /b 1
    )
)
exit /b 0

:CHECK_SENSITIVE_FILES_IGNORED
for %%P in (.env uploads/ backups/ logs/ .codex-run/ contracts.db) do (
    git check-ignore "%%P" > nul 2>&1
    if errorlevel 1 (
        echo [ERRO] Item sensivel nao esta protegido pelo .gitignore: %%P
        exit /b 1
    )
)
exit /b 0

:SET_HAS_CHANGES
set "HAS_CHANGES="
for /f "delims=" %%A in ('git status --porcelain') do set "HAS_CHANGES=1"
exit /b 0

:CHECK_STAGED_SENSITIVE_FILES
set "SENSITIVE_FOUND="
for /f "delims=" %%F in ('git diff --cached --name-only') do (
    set "FILE=%%F"
    if /I "!FILE!"==".env" set "SENSITIVE_FOUND=1"
    if /I "!FILE!"==".env.local" set "SENSITIVE_FOUND=1"
    if /I "!FILE!"==".env.production" set "SENSITIVE_FOUND=1"
    if /I "!FILE!"=="contracts.db" set "SENSITIVE_FOUND=1"
    if /I "!FILE:~-3!"==".db" set "SENSITIVE_FOUND=1"
    if /I "!FILE:~-7!"==".sqlite" set "SENSITIVE_FOUND=1"
    if /I "!FILE:~-8!"==".sqlite3" set "SENSITIVE_FOUND=1"
    if /I "!FILE:~-4!"==".log" set "SENSITIVE_FOUND=1"
    if /I "!FILE:~-4!"==".pyc" set "SENSITIVE_FOUND=1"
    if /I "!FILE:~-4!"==".tmp" set "SENSITIVE_FOUND=1"
    if /I "!FILE:~0,8!"=="uploads/" set "SENSITIVE_FOUND=1"
    if /I "!FILE:~0,8!"=="backups/" set "SENSITIVE_FOUND=1"
    if /I "!FILE:~0,5!"=="logs/" set "SENSITIVE_FOUND=1"
    if /I "!FILE:~0,11!"==".codex-run/" set "SENSITIVE_FOUND=1"
    echo !FILE! | findstr /I "__pycache__" > nul && set "SENSITIVE_FOUND=1"
)
if defined SENSITIVE_FOUND (
    echo [ERRO] O staging contem arquivo local, temporario ou sensivel.
    git diff --cached --name-only
    exit /b 1
)
exit /b 0

:CHECK_STAGED_SECRETS
set "SECRET_REPORT=%TEMP%\contratos_secret_check_%RANDOM%%RANDOM%.txt"
git grep --cached -n -I -E "postgresql://|postgresql\+psycopg2://[^{}]|DB_PASSWORD=.{8,}|APP_SECRET=.{8,}|INITIAL_ADMIN_PASSWORD=.{8,}|\$2[aby]\$[0-9]{2}\$" -- . ":(exclude).env.example" ":(exclude)SECURITY_AUDIT.md" ":(exclude)PERSISTENCE_AUDIT.md" ":(exclude)README.md" ":(exclude)Atualizar Banco e GitHub.bat" > "%SECRET_REPORT%" 2>nul
if not errorlevel 1 (
    echo [ERRO] Possivel segredo encontrado no staging:
    type "%SECRET_REPORT%"
    del "%SECRET_REPORT%" > nul 2>&1
    exit /b 1
)
del "%SECRET_REPORT%" > nul 2>&1
exit /b 0

:CLEAR_GIT_LOCK
if not exist ".git\index.lock" exit /b 0
tasklist /FI "IMAGENAME eq git.exe" 2>nul | find /I "git.exe" >nul
if not errorlevel 1 (
    echo [ERRO] Existe uma operacao Git em andamento.
    echo Feche o Git ou aguarde a operacao terminar e tente novamente.
    exit /b 1
)
echo [AVISO] Removendo trava antiga do Git...
del /F /Q ".git\index.lock" > nul 2>&1
if exist ".git\index.lock" (
    powershell.exe -NoProfile -Command "Remove-Item -LiteralPath '.git\index.lock' -Force -ErrorAction SilentlyContinue" > nul 2>&1
)
if exist ".git\index.lock" (
    echo [ERRO] Nao foi possivel remover .git\index.lock.
    exit /b 1
)
echo [OK] Trava antiga removida.
exit /b 0

:UNSTAGE_ERROR
echo.
echo [AVISO] O commit foi bloqueado por seguranca.
echo Os arquivos permanecem no staging para revisao manual.
goto :ERROR

:TEST_ERROR
echo.
echo [ERRO] Uma validacao falhou. Nada sera publicado.
goto :ERROR

:SUCCESS
echo.
echo Processo concluido com seguranca.
timeout /t 5 > nul
exit /b 0

:ERROR
echo.
echo Processo interrompido. Revise a mensagem acima.
pause
exit /b 1
