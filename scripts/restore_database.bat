@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0.."
set "ENV_FILE=%ROOT_DIR%\.env"

if "%~1"=="" (
    echo Uso: scripts\restore_database.bat caminho\do\backup.dump
    echo Exemplo: scripts\restore_database.bat backups\contratos_db_20260602_103000.dump
    exit /b 1
)

set "BACKUP_FILE=%~1"
if not exist "%BACKUP_FILE%" (
    echo ERRO: Arquivo de backup nao encontrado: "%BACKUP_FILE%".
    exit /b 1
)

if not exist "%ENV_FILE%" (
    echo ERRO: Arquivo .env nao encontrado em "%ENV_FILE%".
    exit /b 1
)

for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    if not "%%A"=="" set "%%A=%%B"
)

if "%DB_HOST%"=="" set "DB_HOST=localhost"
if "%DB_PORT%"=="" set "DB_PORT=5432"
if "%DB_NAME%"=="" (
    echo ERRO: DB_NAME nao definido no .env.
    exit /b 1
)
if "%DB_USER%"=="" (
    echo ERRO: DB_USER nao definido no .env.
    exit /b 1
)
if "%DB_PASSWORD%"=="" (
    echo ERRO: DB_PASSWORD nao definido no .env.
    exit /b 1
)

set "PG_RESTORE_EXE=pg_restore"
where pg_restore >nul 2>nul
if errorlevel 1 (
    set "PG_RESTORE_EXE="
    for /d %%D in ("%ProgramFiles%\PostgreSQL\*") do (
        if exist "%%~fD\bin\pg_restore.exe" set "PG_RESTORE_EXE=%%~fD\bin\pg_restore.exe"
    )
)

if "%PG_RESTORE_EXE%"=="" (
    echo ERRO: pg_restore nao encontrado no PATH.
    echo Adicione a pasta bin do PostgreSQL ao PATH ou instale o PostgreSQL localmente.
    exit /b 1
)

echo ATENCAO: esta operacao restaurara o backup no banco "%DB_NAME%".
echo Arquivo: %BACKUP_FILE%
set /p "CONFIRM=Digite RESTAURAR para continuar: "
if /I not "%CONFIRM%"=="RESTAURAR" (
    echo Restauracao cancelada.
    exit /b 1
)

set "PGPASSWORD=%DB_PASSWORD%"
"%PG_RESTORE_EXE%" -h "%DB_HOST%" -p "%DB_PORT%" -U "%DB_USER%" -d "%DB_NAME%" --clean --if-exists --no-owner "%BACKUP_FILE%"
set "RESTORE_EXIT=%ERRORLEVEL%"
set "PGPASSWORD="

if not "%RESTORE_EXIT%"=="0" (
    echo ERRO: Falha ao restaurar backup.
    exit /b %RESTORE_EXIT%
)

echo Restauracao concluida com sucesso.
exit /b 0
