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
    # Fix: Format string must not have spaces
    $nvsmi = & "nvidia-smi" --query-gpu=memory.free --format=csv, noheader, nounits 2>$null
    if ($LASTEXITCODE -eq 0) {
      $vram = "$([math]::Round($nvsmi / 1024, 1)) GB Free"
      $cuda = "Available (NVIDIA)"
    }
    else {
      # Fallback: Check if an NVIDIA GPU exists at all via CIM
      $gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -like "*NVIDIA*" }
      if ($gpu) {
        $vram = "$($gpu.Name) (SMI missing)"
        $cuda = "Found (Manual/SMI required for live VRAM in this window)"
      }
    }
  }
  catch {}

  return @{ vram = $vram; cuda = $cuda }
}

function Get-OptimizationChoice {
  if (Test-Path $CONFIG_FILE) {
    $cfg = Get-Content $CONFIG_FILE | ConvertFrom-Json
    if ($null -ne $cfg.optimization) { return $cfg.optimization }
  }

  Write-Host "[?] Optimization Selection (Recommended for First Run)" -ForegroundColor Yellow
  Write-Host "Aggressive reuse the game's massive AI libraries (torch) to prevent 5GB+ disk usage."
  
  $opt = "yank"
  
  # Save choice
  $cfg = @{ optimization = $opt }
  $cfg | ConvertTo-Json | Set-Content $CONFIG_FILE
  return $opt
}

function Get-GamePath {
  # 1. Check if we are already inside the game folder (e.g. running from common/AutoDepth...)
  if ($PSScriptRoot -like "*common\AutoDepth Image Viewer*") {
    return (Split-Path $PSScriptRoot -Parent)
  }

  # 2. Check Steam Registry/Library
  try {
    $steamPath = (Get-ItemProperty -Path "HKCU:\SOFTWARE\Valve\Steam" -ErrorAction SilentlyContinue).SteamPath
    if ($steamPath -and (Test-Path "$steamPath\steamapps\libraryfolders.vdf")) {
      $vdf = Get-Content "$steamPath\steamapps\libraryfolders.vdf" -Raw
      $allMatches = [regex]::Matches($vdf, '"path"\s+"([^"]+)"')
      foreach ($m in $allMatches) {
        $libPath = $m.Groups[1].Value.Replace("\\", "\")
        $p = Join-Path $libPath "steamapps\common\AutoDepth Image Viewer"
        if (Test-Path $p) { return $p }
      }
    }
  }
  catch {}

  # 3. Last resort: Fallback to local script root
  return $PSScriptRoot
}

function Get-PythonPath {
  $cfg = if (Test-Path $CONFIG_FILE) { Get-Content $CONFIG_FILE | ConvertFrom-Json } else { @{} }
  if ($null -ne $cfg.python_path -and (Test-Path $cfg.python_path)) {
    Write-Host "[*] Using saved Python path: $($cfg.python_path)" -ForegroundColor Gray
    return $cfg.python_path
  }

  $gamePath = Get-GamePath
  Write-Host "[*] Searching for DA3-compatible Python..." -ForegroundColor Gray
  $candidates = @()
  $candidates += Join-Path $PSScriptRoot "Depth-Anything-3\Python310\python.exe"
  $candidates += Join-Path $gamePath "midas3\Depth-Anything-3\Python310\python.exe"
  $candidates += Join-Path $gamePath "Depth-Anything-3\Python310\python.exe"
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

# --- CONFIG & TRAP ---
$SelectionLoop = $true
trap {
  Write-Host "`n[!] Interrupt detected. Cleaning up AI processes..." -ForegroundColor Red
  Get-Process "python" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*python*" -and $_.CommandLine -like "*midas3_emulator.py*" } | Stop-Process -Force -ErrorAction SilentlyContinue
  exit
}

try {
  # 0. Hardware Analysis
  $hw = Get-HardwareStatus
  
  Write-Host "[*] HARDWARE ANALYSIS (Real-time)" -ForegroundColor Cyan
  Write-Host "  > Current Available VRAM: $($hw.vram)"
  Write-Host "  > CUDA Status:            $($hw.cuda)"
  Write-Host "  > Note: This represents VRAM left while your game/apps are running." -ForegroundColor Gray
  
  if ($hw.cuda -eq "Not Found") {
    Write-Host "`n[!] WARNING: NO CUDA DETECTED" -ForegroundColor Red
    Write-Host "[!] This service will run on CPU, which is EXTREMELY slow." -ForegroundColor Red
    Write-Host "[!] Depth will take 30s+ per image. NVIDIA GPU recommended.`n" -ForegroundColor Red
  }

  Write-Host "[*] Note: You will be asked if you want to run a hardware benchmark after selection." -ForegroundColor Gray

  while ($SelectionLoop) {

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
      & $basePython -c "import torch; print('CUDA:', torch.cuda.is_available())" 2>$null
      $hasTorch = ($LASTEXITCODE -eq 0)
    
      # Verify if CUDA is actually usable by the AI
      $null = & $basePython -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>$null
      if ($LASTEXITCODE -ne 0 -and $hw.cuda -ne "Not Found") {
        Write-Host "`n[!] WARNING: NVIDIA GPU found, but your Python libraries are CPU-ONLY." -ForegroundColor Yellow
        Write-Host "[!] Deep learning performance will be severely limited.`n" -ForegroundColor Yellow
      }
    
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

    # 4. Directories (Game-Resident for Handshake)
    Write-Host "[*] Resolving game communication directories..."
    $gamePath = Get-GamePath
    $inPath = Join-Path $gamePath "Midas3\input"
    $outPath = Join-Path $gamePath "Midas3\output"

    # If game path doesn't have Midas3, fallback to local so the service still runs
    if (-not (Test-Path $inPath)) {
      Write-Host "[!] Game Midas3 folder not found. Using local service directories." -ForegroundColor Gray
      $inPath = Join-Path $PSScriptRoot "input"
      $outPath = Join-Path $PSScriptRoot "output"
    }

    foreach ($p in @($inPath, $outPath)) {
      if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
    }

    # 5. Dependency Check & Top-off
    Write-Host "[*] Verifying/Installing missing components..." -ForegroundColor Yellow
    & $pythonExe -m pip install --upgrade pip | Out-Null
    $reqPath = Join-Path $PSScriptRoot "requirements.txt"
    if (Test-Path $reqPath) {
      & $pythonExe -m pip install -r $reqPath
    }

    # 6. Run
    Write-Host "`n[+] Environment ready. Starting Midas Service..." -ForegroundColor Green
    Write-Host "[!] Note: Ensure Game 'Depth Model' is set to MANUAL for this session.`n" -ForegroundColor Yellow
    Write-Host "[*] Monitoring '$inPath' for requests...`n" -ForegroundColor Gray
  
    $emuArgs = @("--continuous", "--input_path", "$inPath", "--output_path", "$outPath")
  
    # Run and capture exit code
    & $pythonExe (Join-Path $PSScriptRoot "midas3_emulator.py") $emuArgs
  
    $code = $LASTEXITCODE
    if ($code -eq 55) {
      Write-Host "`n[*] Restarting Model Selection..." -ForegroundColor Cyan
      continue
    }
  
    # If we get here, the service stopped normally (or crashed)
    $SelectionLoop = $false

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
