@echo off
setlocal EnableExtensions

cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\scripts\start_system.ps1"
exit /b %ERRORLEVEL%
