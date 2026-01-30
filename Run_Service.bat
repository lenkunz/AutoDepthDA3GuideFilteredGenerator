@echo off
setlocal
cd /d "%~dp0"

REM Trigger the modern PowerShell engine
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_da3.ps1"

if %ERRORLEVEL% neq 0 (
    echo [!] Launcher failed. 
    pause
)