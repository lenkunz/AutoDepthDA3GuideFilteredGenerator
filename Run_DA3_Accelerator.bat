@echo off
setlocal
cd /d "%~dp0"

:: Check for Windows Terminal (wt.exe) and relaunch if not already inside WT
if "%WT_SESSION%"=="" (
    where wt >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        echo [*] Launching in Windows Terminal...
        wt -d "%~dp0" cmd /c "%~f0"
        exit /b
    )
)

:: Configuration
set "DEFAULT_PYTHON=..\Depth-Anything-3\Python310\python.exe"
set "SCRIPT=midas3_emulator.py"
set "CONFIG_FILE=config.json"

:: Try to get python_path from config.json if it exists
if exist "%CONFIG_FILE%" (
    for /f "usebackq tokens=*" %%a in (`powershell -NoProfile -Command "if (Test-Path '%CONFIG_FILE%') { $cfg = Get-Content '%CONFIG_FILE%' | ConvertFrom-Json; if ($cfg.python_path -and (Test-Path $cfg.python_path)) { echo $cfg.python_path } }"`) do (
        set "PYTHON_EXE=%%a"
    )
)

:: Fallback if config check failed or path was invalid
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=%DEFAULT_PYTHON%"

echo [*] Midas DA3 Runner (Manual Console)
echo [*] ================================
echo [*] Python Path: %PYTHON_EXE%
echo [*] Note: Ensure game is in 'Manual' Mode.
echo.

:: 1. Verify existence
if not exist "%PYTHON_EXE%" (
    echo [!] Error: Python environment not found. 
    echo [*] Tried: %PYTHON_EXE%
    echo [*] Please ensure you are in the [Game Root]\midas3\ folder.
    pause
    exit /b
)

if not exist "%SCRIPT%" (
    echo [!] Error: Emulator script not found: %SCRIPT%
    pause
    exit /b
)

:: 2. Launch
echo [*] Starting AI Engine...
"%PYTHON_EXE%" "%SCRIPT%" --continuous --input_path input --output_path output

echo.
echo [*] Engine stopped.
pause
