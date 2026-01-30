@echo off
setlocal
cd /d "%~dp0"

REM 1. Check for Windows Terminal (wt.exe) to provide a premium UI
if "%WT_SESSION%"=="" (
    where wt >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        echo [*] Optimizing UI in Windows Terminal...
        wt -d "%~dp0" cmd /c "%~f0"
        exit /b
    )
)

REM 2. Launch the smart PowerShell engine
REM This handles Python discovery, library "Yanking", and environment setup.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_da3.ps1"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Service failed to start. 
    pause
)
