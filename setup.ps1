# ============================================================================
# Quotex Alert Monitor - Setup Script (Windows PowerShell)
# ============================================================================
# Run: Right-click -> "Run with PowerShell"
# Or:  powershell -ExecutionPolicy Bypass -File setup.ps1
# ============================================================================

$ErrorActionPreference = "Stop"

function Write-Header($msg) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step($msg)  { Write-Host "[STEP] $msg" -ForegroundColor Blue }
function Write-Ok($msg)    { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# ---- Check if running as admin ----
function Test-Admin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# ---- Check if command exists ----
function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# ---- Install Chocolatey (package manager for Windows) ----
function Install-Chocolatey {
    if (Test-Command "choco") {
        Write-Ok "Chocolatey already installed"
        return
    }

    Write-Step "Installing Chocolatey package manager..."
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    Write-Ok "Chocolatey installed"

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# ---- Install Python ----
function Install-Python {
    Write-Header "Python 3.11+"

    if (Test-Command "python") {
        $pyVersion = & python --version 2>&1
        Write-Ok "Python found: $pyVersion"

        # Check version
        $ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
        $major, $minor = $ver -split '\.'
        if ([int]$major -ge 3 -and [int]$minor -ge 8) {
            return
        }
    }

    Write-Step "Installing Python via Chocolatey..."
    choco install python --version=3.12.0 -y --no-progress
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    if (Test-Command "python") {
        Write-Ok "Python installed: $(python --version)"
    } else {
        Write-Err "Python installation failed. Download from https://python.org"
        exit 1
    }
}

# ---- Install Node.js ----
function Install-Node {
    Write-Header "Node.js 20 LTS"

    if (Test-Command "node") {
        $nodeVersion = & node -v 2>&1
        $major = [int]($nodeVersion -replace 'v(\d+)\..*', '$1')
        if ($major -ge 18) {
            Write-Ok "Node.js $nodeVersion found"
            if (Test-Command "npm") { Write-Ok "npm $(npm -v) found" }
            return
        }
    }

    # Try NVM for Windows first
    if (Test-Command "nvm") {
        Write-Step "Installing Node.js 20 via NVM..."
        nvm install 20
        nvm use 20
    } else {
        Write-Step "Installing Node.js via Chocolatey..."
        choco install nodejs-lts -y --no-progress
    }

    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    if (Test-Command "node") {
        Write-Ok "Node.js $(node -v) installed"
    } else {
        Write-Err "Node.js installation failed. Download from https://nodejs.org"
        exit 1
    }
}

# ---- Install MongoDB ----
function Install-MongoDB {
    Write-Header "MongoDB 7.0"

    if (Test-Command "mongod") {
        Write-Ok "MongoDB found"
        # Check if running
        $mongoService = Get-Service -Name "MongoDB" -ErrorAction SilentlyContinue
        if ($mongoService -and $mongoService.Status -eq "Running") {
            Write-Ok "MongoDB service is running"
        } else {
            Write-Warn "MongoDB installed but not running as a service"
            Write-Host "       Start it with: net start MongoDB"
        }
        return
    }

    # Check Docker
    if (Test-Command "docker") {
        $mongoContainer = docker ps 2>&1 | Select-String "mongo"
        if ($mongoContainer) {
            Write-Ok "MongoDB running via Docker"
            return
        }
    }

    Write-Step "Installing MongoDB via Chocolatey..."
    choco install mongodb -y --no-progress 2>&1 | Out-Null

    if (-not (Test-Command "mongod")) {
        if (Test-Command "docker") {
            Write-Step "Falling back to MongoDB via Docker..."
            $existing = docker ps -a --filter "name=quotex-mongo" --format "{{.Names}}" 2>&1
            if ($existing -match "quotex-mongo") {
                docker start quotex-mongo 2>&1 | Out-Null
            } else {
                docker run -d -p 27017:27017 --name quotex-mongo --restart unless-stopped mongo:7
            }
            Write-Ok "MongoDB running via Docker"
        } else {
            Write-Err "MongoDB installation failed."
            Write-Host "       Download from: https://www.mongodb.com/try/download/community"
            Write-Host "       Or install Docker: https://docs.docker.com/desktop/install/windows-install/"
        }
    } else {
        Write-Ok "MongoDB installed"
    }
}

# ---- Setup Backend ----
function Setup-Backend {
    Write-Header "Backend Setup"

    $backendDir = "quotex-alert-monitoring\backend"
    if (-not (Test-Path $backendDir)) {
        Write-Err "Backend directory not found: $backendDir"
        return
    }

    Push-Location $backendDir

    # Create venv
    if (-not (Test-Path "venv")) {
        Write-Step "Creating Python virtual environment..."
        python -m venv venv
    }

    # Activate and install
    Write-Step "Installing Python dependencies..."
    & .\venv\Scripts\Activate.ps1
    pip install --upgrade pip -q 2>&1 | Out-Null
    pip install -r requirements.txt -q 2>&1 | Out-Null
    deactivate

    Write-Ok "Backend dependencies installed"
    Pop-Location
}

# ---- Setup Dashboard ----
function Setup-Dashboard {
    Write-Header "Dashboard Setup"

    $dashDir = "quotex-alert-monitoring\dashboard"
    if (-not (Test-Path $dashDir)) {
        Write-Err "Dashboard directory not found: $dashDir"
        return
    }

    Push-Location $dashDir
    Write-Step "Installing npm dependencies..."
    npm install --silent 2>&1 | Out-Null
    Write-Ok "Dashboard dependencies installed"
    Pop-Location
}

# ---- Setup Extension ----
function Setup-Extension {
    Write-Header "Chrome Extension Setup"

    $extDir = "quotex-alert-monitoring\extension"
    if (-not (Test-Path $extDir)) {
        Write-Err "Extension directory not found: $extDir"
        return
    }

    Push-Location $extDir
    Write-Step "Installing npm dependencies..."
    npm install --silent 2>&1 | Out-Null

    Write-Step "Building extension..."
    npx vite build

    # Generate icons
    if (-not (Test-Path "dist\icons\icon-128.png")) {
        Write-Step "Generating icons..."
        New-Item -ItemType Directory -Force -Path "dist\icons" | Out-Null
        python -c @"
import struct, zlib
def make_png(size, r, g, b):
    raw = b''
    for y in range(size):
        raw += b'\x00'
        for x in range(size):
            cx, cy = size/2, size/2
            radius = size * 0.4
            dx, dy = x - cx, y - cy
            dist = (dx*dx + dy*dy) ** 0.5
            if dist < radius:
                if dist > radius * 0.6: raw += bytes([r, g, b, 255])
                else: raw += bytes([40, 40, 50, 255])
            elif size*0.35 < x < size*0.65 and size*0.45 < y < size*0.75 and x > cx:
                raw += bytes([r, g, b, 255])
            else: raw += bytes([0, 0, 0, 0])
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
for s in [16, 48, 128]:
    with open(f'dist/icons/icon-{s}.png', 'wb') as f: f.write(make_png(s, 0x3f, 0xb9, 0x50))
"@
    }

    Write-Ok "Extension built at: $extDir\dist\"
    Pop-Location
}

# ---- Create run script ----
function Create-RunScript {
    Write-Header "Creating Run Script"

    @'
@echo off
REM ============================================================================
REM Quotex Alert Monitor - Start All Services (Windows)
REM ============================================================================

echo.
echo ========================================
echo   Quotex Alert Monitor - Starting...
echo ========================================
echo.

REM Check MongoDB
echo [1/3] Checking MongoDB...
sc query MongoDB >nul 2>&1
if %errorlevel%==0 (
    echo   MongoDB service found
) else (
    docker ps 2>nul | findstr mongo >nul 2>&1
    if %errorlevel%==0 (
        echo   MongoDB running via Docker
    ) else (
        echo   [ERROR] MongoDB is not running!
        echo   Start it with: net start MongoDB
        echo   Or: docker run -d -p 27017:27017 --name quotex-mongo mongo:7
        pause
        exit /b 1
    )
)

REM Start Backend
echo.
echo [2/3] Starting Backend on port 8000...
cd quotex-alert-monitoring\backend
start "Quotex Backend" cmd /c "venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"
cd ..\..
timeout /t 3 /nobreak >nul

REM Start Dashboard
echo.
echo [3/3] Starting Dashboard on port 5173...
cd quotex-alert-monitoring\dashboard
start "Quotex Dashboard" cmd /c "npm run dev"
cd ..\..
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   All services running!
echo ========================================
echo.
echo   Backend:    http://localhost:8000
echo   Dashboard:  http://localhost:5173
echo   Health:     http://localhost:8000/health
echo.
echo   Extension:  Load quotex-alert-monitoring\extension\dist\ in Chrome
echo               chrome://extensions/ -^> Load unpacked
echo.
echo   Press any key to stop all services...
pause >nul

REM Stop services
taskkill /FI "WINDOWTITLE eq Quotex Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Quotex Dashboard" /F >nul 2>&1
echo Services stopped.
'@ | Out-File -FilePath "run.bat" -Encoding ASCII

    Write-Ok "Created run.bat (starts all services on Windows)"
}

# ---- Summary ----
function Show-Summary {
    Write-Header "Setup Complete!"

    Write-Host "  All dependencies installed and configured." -ForegroundColor Green
    Write-Host ""
    Write-Host "  To start all services:" -ForegroundColor Cyan
    Write-Host "    .\run.bat" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Or start individually:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "    # Terminal 1 - Backend" -ForegroundColor Yellow
    Write-Host "    cd quotex-alert-monitoring\backend"
    Write-Host "    .\venv\Scripts\Activate.ps1"
    Write-Host "    uvicorn app.main:app --host 0.0.0.0 --port 8000"
    Write-Host ""
    Write-Host "    # Terminal 2 - Dashboard" -ForegroundColor Yellow
    Write-Host "    cd quotex-alert-monitoring\dashboard"
    Write-Host "    npm run dev"
    Write-Host ""
    Write-Host "  Chrome Extension:" -ForegroundColor Cyan
    Write-Host "    1. Open chrome://extensions/"
    Write-Host "    2. Enable Developer mode"
    Write-Host "    3. Load unpacked -> quotex-alert-monitoring\extension\dist\"
    Write-Host "    4. Open a Quotex trading page"
    Write-Host ""
    Write-Host "  Dashboard:  http://localhost:5173" -ForegroundColor Green
    Write-Host "  Backend:    http://localhost:8000/health" -ForegroundColor Green
    Write-Host ""
}

# ============================================================================
# MAIN
# ============================================================================

Write-Header "Quotex Alert Monitor - Setup"

# Check admin
if (-not (Test-Admin)) {
    Write-Warn "Not running as Administrator. Some installations may fail."
    Write-Host "       Right-click PowerShell -> 'Run as Administrator' for best results."
    Write-Host ""
}

# Move to script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Install-Chocolatey
Install-Python
Install-Node
Install-MongoDB
Setup-Backend
Setup-Dashboard
Setup-Extension
Create-RunScript
Show-Summary
