# PowerShell Launcher for AutoDepth DA3 Service
# ---------------------------------------------

$ErrorActionPreference = "Stop"

Write-Host "`n[*] Midas DA3 Setup and Runner (PowerShell Engine)" -ForegroundColor Cyan
Write-Host "[*] ============================================" -ForegroundColor Cyan
Write-Host ""

$CONFIG_FILE = Join-Path $PSScriptRoot "config.json"

function Get-HardwareStatus {
  $vram = "Unknown"
  $cuda = "Not Found"
  
  # Try to get VRAM via NVIDIA-SMI if available
  try {
    $nvsmi = & "nvidia-smi" --query-gpu=memory.free --format=csv, noheader, nounits 2>$null
    if ($LASTEXITCODE -eq 0) {
      $vram = "$([math]::Round($nvsmi / 1024, 1)) GB Free"
      $cuda = "Available (NVIDIA)"
    }
  }
  catch {}

  return @{ vram = $vram; cuda = $cuda }
}

function Select-Model {
  Write-Host "`n[?] MODEL SELECTION" -ForegroundColor Yellow
  Write-Host "--------------------------------------------------------"
  Write-Host "[1] DA3-Giant (~2.5 GB Model)"
  Write-Host "    - VRAM: ~4.5GB (512px) | ~8.5GB (1024px)"
  Write-Host "[2] DA3-Large (~0.8 GB Model)"
  Write-Host "    - VRAM: ~1.8GB (512px) | ~3.5GB (1024px)"
  Write-Host "Note: Estimates represent total app VRAM usage."
  
  $choice = ""
  while ($choice -notmatch "^[12]$") {
    $choice = (Read-Host "Select [1-2]").Trim()
  }
  
  return if ($choice -eq "1") { "da3-giant" } else { "da3-large" }
}

function Get-CacheChoice {
  Write-Host "`n[?] SAVE DEPTH LOCALLY?" -ForegroundColor Yellow
  Write-Host "--------------------------------------------------------"
  Write-Host "(This allows the mod to 'remember' depth for faster loading)"
  $choice = Read-Host "[y/N]"
  return ($choice -eq "y")
}

function Get-OptimizationChoice {
  if (Test-Path $CONFIG_FILE) {
    $cfg = Get-Content $CONFIG_FILE | ConvertFrom-Json
    if ($null -ne $cfg.optimization) { return $cfg.optimization }
  }

  Write-Host "[?] Optimization Selection (Recommended for First Run)" -ForegroundColor Yellow
  Write-Host "Aggressive reuse the game's massive AI libraries (torch) to save 5GB+ disk space."
    
  $opt = "yank"
    
  # Save choice
  $cfg = @{ optimization = $opt }
  $cfg | ConvertTo-Json | Set-Content $CONFIG_FILE
    
  return $opt
}

function Get-PythonPath {
  $cfg = if (Test-Path $CONFIG_FILE) { Get-Content $CONFIG_FILE | ConvertFrom-Json } else { @{} }
  if ($null -ne $cfg.python_path -and (Test-Path $cfg.python_path)) {
    Write-Host "[*] Using saved Python path: $($cfg.python_path)" -ForegroundColor Gray
    return $cfg.python_path
  }

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

function Save-PythonPath ($path) {
  $cfg = if (Test-Path $CONFIG_FILE) { Get-Content $CONFIG_FILE | ConvertFrom-Json -ErrorAction SilentlyContinue } else { @{} }
  if ($null -eq $cfg) { $cfg = @{} }
  
  $cfg_obj = [ordered]@{
    optimization = if ($null -ne $cfg.optimization) { $cfg.optimization } else { "yank" }
    python_path  = $path
  }
  
  $cfg_obj | ConvertTo-Json | Set-Content $CONFIG_FILE
}

try {
  # 0. Hardware Analysis
  $hw = Get-HardwareStatus
  
  Write-Host "[*] HARDWARE ANALYSIS" -ForegroundColor Cyan
  Write-Host "  > VRAM: $($hw.vram)"
  Write-Host "  > CUDA: $($hw.cuda)"
  
  if ($hw.cuda -eq "Not Found") {
    Write-Host "`n[!] WARNING: NO CUDA DETECTED" -ForegroundColor Red
    Write-Host "[!] This service will run on CPU, which is EXTREMELY slow." -ForegroundColor Red
    Write-Host "[!] Depth will take 30s+ per image. NVIDIA GPU recommended.`n" -ForegroundColor Red
  }

  # 1. Start setup
  $opt = Get-OptimizationChoice
  $model = Select-Model
  $doCache = Get-CacheChoice
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
  Save-PythonPath $basePython

  # 2. Check for capacity (Venv & Yanking)
  Write-Host "[*] Verifying environment compatibility..."
  $hasVenvMod = $false
  $hasTorch = $false
  
  try {
    $oldEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    
    # Check venv
    & $basePython -c "import venv; print('OK')" 2>$null
    $hasVenvMod = ($LASTEXITCODE -eq 0)
    
    # Check torch
    & $basePython -c "import torch; print('OK')" 2>$null
    $hasTorch = ($LASTEXITCODE -eq 0)
    
    $ErrorActionPreference = $oldEAP
  }
  catch {
    # Ignore errors during compatibility check, we just need $hasVenvMod/$hasTorch
  }

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

  # 4. Directories (Service-local)
  Write-Host "[*] Ensuring communication directories exist..."
  $inPath = Join-Path $PSScriptRoot "input"
  $outPath = Join-Path $PSScriptRoot "output"

  foreach ($dir in @("input", "output")) {
    $path = Join-Path $PSScriptRoot $dir
    if (-not (Test-Path $path)) { New-Item -ItemType Directory -Path $path | Out-Null }
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
  Write-Host "[!] Note: Ensure Game 'Depth Model' is set to MANUAL for this session.`n" -ForegroundColor Yellow
  Write-Host "[*] Monitoring '$inPath' for requests...`n" -ForegroundColor Gray
  
  $emuArgs = @("--continuous", "--input_path", "$inPath", "--output_path", "$outPath", "--model_name", "$model")
  if ($doCache) { $emuArgs += "--cache" }
  
  & $pythonExe (Join-Path $PSScriptRoot "midas3_emulator.py") $emuArgs

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
