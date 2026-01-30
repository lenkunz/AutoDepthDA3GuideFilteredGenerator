# PowerShell Launcher for AutoDepth DA3 Service
# ---------------------------------------------

$ErrorActionPreference = "Stop"

Write-Host "`n[*] Midas DA3 Setup and Runner (PowerShell Engine)" -ForegroundColor Cyan
Write-Host "[*] ============================================" -ForegroundColor Cyan
Write-Host ""

$CONFIG_FILE = Join-Path $PSScriptRoot "config.json"

function Get-OptimizationChoice {
  if (Test-Path $CONFIG_FILE) {
    $cfg = Get-Content $CONFIG_FILE | ConvertFrom-Json
    if ($null -ne $cfg.optimization) { return $cfg.optimization }
  }

  Write-Host "[?] Optimization Selection (Recommended for First Run)" -ForegroundColor Yellow
  Write-Host "Aggressive Yanking can reuse the game's massive AI libraries (torch) to save 5GB+ disk space."
  Write-Host "[1] Aggressive Yanking (Shared Libraries / Thin 10MB env / Fast)"
  Write-Host "[2] Fresh Environment (Isolated Download / Full 5GB env / Slow)"
    
  $choice = ""
  while ($choice -notmatch "^[12]$") {
    $choice = (Read-Host "Select [1-2]").Trim()
  }

  $opt = if ($choice -eq "1") { "yank" } else { "fresh" }
    
  # Save choice
  $cfg = @{ optimization = $opt }
  $cfg | ConvertTo-Json | Set-Content $CONFIG_FILE
    
  return $opt
}

function Get-PythonPath {
  Write-Host "[*] Searching for DA3-compatible Python..." -ForegroundColor Gray
  $candidates = @()
  # local/parent
  $candidates += Join-Path $PSScriptRoot "Depth-Anything-3\Python310\python.exe"
  $candidates += Join-Path (Split-Path $PSScriptRoot -Parent) "Depth-Anything-3\Python310\python.exe"
  # steam
  try {
    $steamPath = (Get-ItemProperty -Path "HKCU:\SOFTWARE\Valve\Steam" -ErrorAction SilentlyContinue).SteamPath
    if ($steamPath -and (Test-Path "$steamPath\steamapps\libraryfolders.vdf")) {
      $vdf = Get-Content "$steamPath\steamapps\libraryfolders.vdf" -Raw
      $allMatches = [regex]::Matches($vdf, '"path"\s+"([^"]+)"')
      foreach ($m in $allMatches) {
        $libPath = $m.Groups[1].Value
        $candidates += Join-Path $libPath "steamapps\common\AutoDepth Image Viewer\midas3\Depth-Anything-3\Python310\python.exe"
      }
    }
  }
  catch {}
  # system
  $candidates += "python"

  foreach ($path in $candidates) {
    if ($path -eq "python") {
      try { python --version >$null 2>$null; if ($LASTEXITCODE -eq 0) { return "python" } } catch {}
    }
    elseif (Test-Path $path) {
      return $path
    }
  }
  return $null
}

try {
  # 1. Start setup
  $opt = Get-OptimizationChoice
  $basePython = Get-PythonPath

  while ($null -eq $basePython) {
    Write-Host "[!] No Python interpreter found." -ForegroundColor Yellow
    Write-Host "Please choose an option:"
    Write-Host "[1] Provide a manual path to python.exe"
    Write-Host "[2] Exit and install Python 3.10+ from python.org"
    $choice = Read-Host "Select [1-2]"
    if ($choice -eq "1") {
      $manual = Read-Host "Enter full path to python.exe"
      if (Test-Path $manual) { $basePython = $manual }
      else { Write-Host "[!] Path not found: $manual" -ForegroundColor Red }
    }
    else { exit 1 }
  }

  Write-Host "[+] Base Python: $basePython" -ForegroundColor Green

  # 2. Check for capacity (Venv & Yanking)
  Write-Host "[*] Verifying environment compatibility..."
  $null = & $basePython -c "import venv; print('OK')" 2>$null
  $hasVenvMod = ($LASTEXITCODE -eq 0)
  $null = & $basePython -c "import torch; print('OK')" 2>$null
  $hasTorch = ($LASTEXITCODE -eq 0)

  $venvPath = Join-Path $PSScriptRoot "env"
  $pythonExe = Join-Path $venvPath "Scripts\python.exe"

  if ($opt -eq "yank" -and $hasTorch -and (-not (Test-Path $pythonExe))) {
    # Check if we should do a DIRECT RUN instead of venv (if venv mod is missing)
    if (-not $hasVenvMod) {
      Write-Host "[!] Yanking: Base Python lacks 'venv' module but has 'torch'. Switching to Direct Run." -ForegroundColor Gray
      $pythonExe = $basePython
    }
    else {
      Write-Host "[*] Creating thin virtual environment (Reusing shared libraries)..." -ForegroundColor Yellow
      & $basePython -m venv env --system-site-packages
      $pythonExe = Join-Path $venvPath "Scripts\python.exe"
    }
  }
  elseif (-not (Test-Path $pythonExe)) {
    if (-not $hasVenvMod) {
      Write-Error "The chosen Python ($basePython) lacks the 'venv' module and required dependencies."
    }
    Write-Host "[*] Creating fresh virtual environment..." -ForegroundColor Yellow
    & $basePython -m venv env
    $pythonExe = Join-Path $venvPath "Scripts\python.exe"
  }

  # 4. Directories (Parent-relative for game integration)
  Write-Host "[*] Ensuring communication directories exist..."
  $parentDir = Split-Path $PSScriptRoot -Parent
  $inPath = Join-Path $parentDir "input"
  $outPath = Join-Path $parentDir "output"

  foreach ($dirPath in @($inPath, $outPath)) {
    if (-not (Test-Path $dirPath)) { New-Item -ItemType Directory -Path $dirPath | Out-Null }
  }

  # 5. Dependency Check & Top-off
  Write-Host "[*] Verifying/Installing missing components..." -ForegroundColor Yellow
  & $pythonExe -m pip install --upgrade pip | Out-Null
  $reqPath = Join-Path $PSScriptRoot "requirements.txt"
  if (Test-Path $reqPath) {
    & $pythonExe -m pip install -r $reqPath
  }

  # 6. Run
  Write-Host "`n[+] Environment ready. Starting DA3 Service..." -ForegroundColor Green
  Write-Host "[*] Monitoring '$inPath' for requests...`n" -ForegroundColor Gray

  # Set CWD to game root so image paths in .txt files resolve correctly
  Push-Location $parentDir
  try {
    & $pythonExe (Join-Path $PSScriptRoot "midas3_emulator.py") --continuous --input_path "$inPath" --output_path "$outPath"
  }
  finally {
    Pop-Location
  }

}
catch {
  Write-Host "`n[!] SETUP FAILED: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "[?] It's possible the 'Yank' or 'Fresh' choice was incompatible with your Python distribution."
  $reset = Read-Host "Would you like to RESET the configuration and try again next run? (y/n)"
  if ($reset -eq 'y') {
    Remove-Item $CONFIG_FILE -ErrorAction SilentlyContinue
    Write-Host "[*] Configuration reset. Please re-run the launcher."
  }
  Pause
  exit 1
}

Write-Host "`n[*] Service stopped."
Pause
