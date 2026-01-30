@echo off
setlocal
cd /d "%~dp0"

REM Check for Windows Terminal (wt.exe)
where wt >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [*] Launching in Windows Terminal...
    wt -d "%~dp0" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_da3.ps1"
    exit /b
)

REM Fallback to standard console
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_da3.ps1"

if %ERRORLEVEL% neq 0 (
    echo [!] Launcher failed. 
    pause
)