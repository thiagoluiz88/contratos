@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0.."
set "ENV_FILE=%ROOT_DIR%\.env"
set "BACKUP_DIR=%ROOT_DIR%\backups"

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

set "PG_DUMP_EXE=pg_dump"
where pg_dump >nul 2>nul
if errorlevel 1 (
    set "PG_DUMP_EXE="
    for /d %%D in ("%ProgramFiles%\PostgreSQL\*") do (
        if exist "%%~fD\bin\pg_dump.exe" set "PG_DUMP_EXE=%%~fD\bin\pg_dump.exe"
    )
)

if "%PG_DUMP_EXE%"=="" (
    echo ERRO: pg_dump nao encontrado no PATH.
    echo Adicione a pasta bin do PostgreSQL ao PATH ou instale o PostgreSQL localmente.
    exit /b 1
)

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "BACKUP_FILE=%BACKUP_DIR%\%DB_NAME%_%STAMP%.dump"

if exist "%BACKUP_FILE%" (
    echo ERRO: Arquivo de backup ja existe: "%BACKUP_FILE%".
    exit /b 1
)

echo Gerando backup PostgreSQL...
echo Banco: %DB_NAME%
echo Destino: %BACKUP_FILE%

set "PGPASSWORD=%DB_PASSWORD%"
"%PG_DUMP_EXE%" -h "%DB_HOST%" -p "%DB_PORT%" -U "%DB_USER%" -d "%DB_NAME%" -F c -f "%BACKUP_FILE%"
set "DUMP_EXIT=%ERRORLEVEL%"
set "PGPASSWORD="

if not "%DUMP_EXIT%"=="0" (
    echo ERRO: Falha ao gerar backup.
    if exist "%BACKUP_FILE%" del "%BACKUP_FILE%"
    exit /b %DUMP_EXIT%
)

echo Backup concluido com sucesso.
echo %BACKUP_FILE%
exit /b 0
