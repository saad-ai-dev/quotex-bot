#!/usr/bin/env bash
# ============================================================================
# Quotex Alert Monitor - Universal Setup Script (Linux / macOS)
# ============================================================================
# This script installs all dependencies and sets up the project.
# Run: chmod +x setup.sh && ./setup.sh
# ============================================================================

set -e

# ---- Colors ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() { echo -e "\n${CYAN}========================================${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}========================================${NC}\n"; }
print_step()   { echo -e "${BLUE}[STEP]${NC} $1"; }
print_ok()     { echo -e "${GREEN}[OK]${NC} $1"; }
print_warn()   { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_err()    { echo -e "${RED}[ERROR]${NC} $1"; }
print_info()   { echo -e "       $1"; }

# ---- Detect OS ----
detect_os() {
    case "$(uname -s)" in
        Linux*)   OS="linux";;
        Darwin*)  OS="mac";;
        CYGWIN*|MINGW*|MSYS*) OS="windows";;
        *)        OS="unknown";;
    esac

    # Detect Linux distro
    if [ "$OS" = "linux" ]; then
        if command -v apt-get &>/dev/null; then
            PKG_MANAGER="apt"
        elif command -v dnf &>/dev/null; then
            PKG_MANAGER="dnf"
        elif command -v yum &>/dev/null; then
            PKG_MANAGER="yum"
        elif command -v pacman &>/dev/null; then
            PKG_MANAGER="pacman"
        elif command -v zypper &>/dev/null; then
            PKG_MANAGER="zypper"
        else
            PKG_MANAGER="unknown"
        fi
    elif [ "$OS" = "mac" ]; then
        PKG_MANAGER="brew"
    fi

    echo -e "${GREEN}Detected OS:${NC} $OS"
    [ "$OS" = "linux" ] && echo -e "${GREEN}Package Manager:${NC} $PKG_MANAGER"
}

# ---- Install system package ----
install_pkg() {
    local pkg="$1"
    print_step "Installing $pkg..."
    case "$PKG_MANAGER" in
        apt)     sudo apt-get update -qq && sudo apt-get install -y -qq "$pkg" ;;
        dnf)     sudo dnf install -y -q "$pkg" ;;
        yum)     sudo yum install -y -q "$pkg" ;;
        pacman)  sudo pacman -S --noconfirm --needed "$pkg" ;;
        zypper)  sudo zypper install -y "$pkg" ;;
        brew)    brew install "$pkg" ;;
        *)       print_err "Unknown package manager. Please install $pkg manually."; return 1 ;;
    esac
}

# ---- Check and install Python ----
setup_python() {
    print_header "Python 3.11+"

    if command -v python3 &>/dev/null; then
        PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
            print_ok "Python $PY_VERSION found"
            return 0
        else
            print_warn "Python $PY_VERSION found but 3.11+ recommended"
            # Still usable if >= 3.8
            if [ "$PY_MINOR" -ge 8 ]; then
                print_info "Python $PY_VERSION is compatible, continuing..."
                return 0
            fi
        fi
    fi

    print_step "Installing Python..."
    case "$OS" in
        linux)
            case "$PKG_MANAGER" in
                apt)
                    sudo apt-get update -qq
                    sudo apt-get install -y -qq python3 python3-pip python3-venv
                    ;;
                dnf)     sudo dnf install -y python3 python3-pip ;;
                yum)     sudo yum install -y python3 python3-pip ;;
                pacman)  sudo pacman -S --noconfirm python python-pip ;;
                zypper)  sudo zypper install -y python3 python3-pip ;;
            esac
            ;;
        mac)
            if command -v brew &>/dev/null; then
                brew install python@3.12
            else
                print_err "Homebrew not found. Install it first: https://brew.sh"
                return 1
            fi
            ;;
    esac

    # Verify
    if command -v python3 &>/dev/null; then
        print_ok "Python $(python3 --version 2>&1 | awk '{print $2}') installed"
    else
        print_err "Python installation failed. Please install manually."
        return 1
    fi
}

# ---- Check and install pip ----
setup_pip() {
    if python3 -m pip --version &>/dev/null; then
        print_ok "pip found"
        return 0
    fi

    print_step "Installing pip..."
    case "$OS" in
        linux)
            case "$PKG_MANAGER" in
                apt) sudo apt-get install -y -qq python3-pip ;;
                *)   python3 -m ensurepip --upgrade 2>/dev/null || curl -sS https://bootstrap.pypa.io/get-pip.py | python3 ;;
            esac
            ;;
        mac) python3 -m ensurepip --upgrade ;;
    esac
    print_ok "pip installed"
}

# ---- Check and install NVM + Node.js ----
setup_node() {
    print_header "Node.js 18+ (via NVM)"

    # Check if Node is already available
    if command -v node &>/dev/null; then
        NODE_VERSION=$(node -v | tr -d 'v')
        NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
        if [ "$NODE_MAJOR" -ge 18 ]; then
            print_ok "Node.js v$NODE_VERSION found"
            # Check npm
            if command -v npm &>/dev/null; then
                print_ok "npm $(npm -v) found"
            fi
            return 0
        else
            print_warn "Node.js v$NODE_VERSION found but 18+ required"
        fi
    fi

    # Install NVM if not present
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

    if [ ! -d "$NVM_DIR" ] || ! command -v nvm &>/dev/null; then
        print_step "Installing NVM..."
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

        # Load NVM
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    else
        # Load NVM
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        print_ok "NVM already installed"
    fi

    # Install Node 20 LTS
    print_step "Installing Node.js 20 LTS via NVM..."
    nvm install 20
    nvm use 20
    nvm alias default 20

    print_ok "Node.js $(node -v) installed"
    print_ok "npm $(npm -v) installed"
}

# ---- Check and install MongoDB ----
setup_mongodb() {
    print_header "MongoDB 7.0"

    # Check if mongod is available
    if command -v mongod &>/dev/null; then
        MONGO_VERSION=$(mongod --version 2>/dev/null | head -1 | grep -oP 'v\d+\.\d+\.\d+' || echo "unknown")
        print_ok "MongoDB $MONGO_VERSION found"

        # Check if running
        if pgrep -x mongod &>/dev/null || systemctl is-active mongod &>/dev/null 2>&1; then
            print_ok "MongoDB is running"
        else
            print_warn "MongoDB is installed but not running"
            print_info "Start it with: sudo systemctl start mongod"
            print_info "Or:            mongod --dbpath /data/db --fork --logpath /tmp/mongod.log"
        fi
        return 0
    fi

    # Check if running via Docker
    if command -v docker &>/dev/null && docker ps 2>/dev/null | grep -q mongo; then
        print_ok "MongoDB running via Docker"
        return 0
    fi

    print_step "Installing MongoDB..."
    case "$OS" in
        linux)
            case "$PKG_MANAGER" in
                apt)
                    # Ubuntu/Debian - official MongoDB repo
                    print_info "Adding MongoDB repository..."
                    curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg 2>/dev/null || true

                    UBUNTU_CODENAME=$(lsb_release -cs 2>/dev/null || echo "jammy")
                    echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu ${UBUNTU_CODENAME}/mongodb-org/7.0 multiverse" | \
                        sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list > /dev/null

                    sudo apt-get update -qq
                    sudo apt-get install -y -qq mongodb-org || {
                        print_warn "Official MongoDB install failed, trying community package..."
                        sudo apt-get install -y -qq mongodb || {
                            print_warn "Package install failed. Trying Docker fallback..."
                            setup_mongodb_docker
                            return $?
                        }
                    }
                    sudo systemctl enable mongod 2>/dev/null || true
                    sudo systemctl start mongod 2>/dev/null || true
                    ;;
                dnf|yum)
                    cat <<'REPO' | sudo tee /etc/yum.repos.d/mongodb-org-7.0.repo > /dev/null
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/9/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-7.0.asc
REPO
                    sudo $PKG_MANAGER install -y mongodb-org || setup_mongodb_docker
                    sudo systemctl enable mongod 2>/dev/null || true
                    sudo systemctl start mongod 2>/dev/null || true
                    ;;
                pacman)
                    # Arch - use AUR or Docker
                    print_warn "MongoDB not in official Arch repos. Using Docker..."
                    setup_mongodb_docker
                    return $?
                    ;;
                *)
                    setup_mongodb_docker
                    return $?
                    ;;
            esac
            ;;
        mac)
            if command -v brew &>/dev/null; then
                brew tap mongodb/brew
                brew install mongodb-community@7.0
                brew services start mongodb-community@7.0
            else
                print_err "Install Homebrew first: https://brew.sh"
                return 1
            fi
            ;;
    esac

    # Verify
    if command -v mongod &>/dev/null || (command -v docker &>/dev/null && docker ps | grep -q mongo); then
        print_ok "MongoDB installed"
    else
        print_err "MongoDB installation failed"
        print_info "You can install it manually or use Docker:"
        print_info "  docker run -d -p 27017:27017 --name quotex-mongo mongo:7"
        return 1
    fi
}

# ---- Fallback: MongoDB via Docker ----
setup_mongodb_docker() {
    if ! command -v docker &>/dev/null; then
        print_err "Docker not found. Please install MongoDB or Docker manually."
        print_info "MongoDB: https://www.mongodb.com/docs/manual/installation/"
        print_info "Docker:  https://docs.docker.com/engine/install/"
        return 1
    fi

    print_step "Starting MongoDB via Docker..."
    if docker ps -a | grep -q quotex-mongo; then
        docker start quotex-mongo 2>/dev/null || true
    else
        docker run -d -p 27017:27017 --name quotex-mongo --restart unless-stopped mongo:7
    fi
    print_ok "MongoDB running via Docker on port 27017"
}

# ---- Setup Backend ----
setup_backend() {
    print_header "Backend Setup"

    local BACKEND_DIR="quotex-alert-monitoring/backend"

    if [ ! -d "$BACKEND_DIR" ]; then
        print_err "Backend directory not found: $BACKEND_DIR"
        return 1
    fi

    cd "$BACKEND_DIR"

    # Create virtual environment
    if [ ! -d "venv" ]; then
        print_step "Creating Python virtual environment..."
        python3 -m venv venv 2>/dev/null || {
            print_warn "python3-venv not installed, installing..."
            PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            case "$PKG_MANAGER" in
                apt) sudo apt-get install -y -qq "python${PY_VER}-venv" python3-venv ;;
                dnf|yum) sudo $PKG_MANAGER install -y python3-virtualenv ;;
                pacman) sudo pacman -S --noconfirm python-virtualenv ;;
                *) pip3 install virtualenv ;;
            esac
            python3 -m venv venv
        }
        print_ok "Virtual environment created"
    else
        print_ok "Virtual environment exists"
    fi

    # Activate and install deps
    print_step "Installing Python dependencies..."
    source venv/bin/activate
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    deactivate

    print_ok "Backend dependencies installed"
    cd - > /dev/null
}

# ---- Setup Dashboard ----
setup_dashboard() {
    print_header "Dashboard Setup"

    local DASHBOARD_DIR="quotex-alert-monitoring/dashboard"

    if [ ! -d "$DASHBOARD_DIR" ]; then
        print_err "Dashboard directory not found: $DASHBOARD_DIR"
        return 1
    fi

    cd "$DASHBOARD_DIR"

    # Load NVM if needed
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

    print_step "Installing npm dependencies..."
    npm install --silent 2>/dev/null
    print_ok "Dashboard dependencies installed"

    cd - > /dev/null
}

# ---- Setup Extension ----
setup_extension() {
    print_header "Chrome Extension Setup"

    local EXT_DIR="quotex-alert-monitoring/extension"

    if [ ! -d "$EXT_DIR" ]; then
        print_err "Extension directory not found: $EXT_DIR"
        return 1
    fi

    cd "$EXT_DIR"

    # Load NVM if needed
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

    print_step "Installing npm dependencies..."
    npm install --silent 2>/dev/null

    print_step "Building extension..."
    npx vite build

    # Generate icons if missing
    if [ ! -f "dist/icons/icon-128.png" ]; then
        print_step "Generating extension icons..."
        mkdir -p dist/icons
        python3 -c "
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
                if dist > radius * 0.6:
                    raw += bytes([r, g, b, 255])
                else:
                    raw += bytes([40, 40, 50, 255])
            elif size*0.35 < x < size*0.65 and size*0.45 < y < size*0.75 and x > cx:
                raw += bytes([r, g, b, 255])
            else:
                raw += bytes([0, 0, 0, 0])
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
for s in [16, 48, 128]:
    with open(f'dist/icons/icon-{s}.png', 'wb') as f:
        f.write(make_png(s, 0x3f, 0xb9, 0x50))
"
    fi

    print_ok "Extension built at: $EXT_DIR/dist/"

    cd - > /dev/null
}

# ---- Create run script ----
create_run_script() {
    print_header "Creating Run Script"

    cat > run.sh << 'RUNSCRIPT'
#!/usr/bin/env bash
# ============================================================================
# Quotex Alert Monitor - Start All Services
# ============================================================================
# Usage: ./run.sh
# Starts MongoDB check, Backend, and Dashboard in background.
# Press Ctrl+C to stop all services.
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

cleanup() {
    echo -e "\n${CYAN}Stopping all services...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Quotex Alert Monitor - Starting...    ${NC}"
echo -e "${CYAN}========================================${NC}"

# Check MongoDB
echo -e "\n${CYAN}[1/3] Checking MongoDB...${NC}"
if pgrep -x mongod &>/dev/null || systemctl is-active mongod &>/dev/null 2>&1; then
    echo -e "${GREEN}  MongoDB is running${NC}"
elif command -v docker &>/dev/null && docker ps 2>/dev/null | grep -q mongo; then
    echo -e "${GREEN}  MongoDB running via Docker${NC}"
else
    echo -e "${RED}  MongoDB is NOT running!${NC}"
    echo -e "  Start it with one of:"
    echo -e "    sudo systemctl start mongod"
    echo -e "    docker run -d -p 27017:27017 --name quotex-mongo mongo:7"
    echo -e "    mongod --dbpath /data/db --fork --logpath /tmp/mongod.log"
    exit 1
fi

# Load NVM
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Start Backend
echo -e "\n${CYAN}[2/3] Starting Backend on port 8000...${NC}"
cd "$PROJECT_DIR/quotex-alert-monitoring/backend"
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/quotex-backend.log 2>&1 &
PIDS+=($!)
echo -e "${GREEN}  Backend PID: ${PIDS[-1]}${NC}"
sleep 2

# Verify backend
if curl -s http://localhost:8000/health | grep -q '"ok"'; then
    echo -e "${GREEN}  Backend healthy${NC}"
else
    echo -e "${RED}  Backend failed to start! Check /tmp/quotex-backend.log${NC}"
fi

# Start Dashboard
echo -e "\n${CYAN}[3/3] Starting Dashboard on port 5173...${NC}"
cd "$PROJECT_DIR/quotex-alert-monitoring/dashboard"
npm run dev > /tmp/quotex-dashboard.log 2>&1 &
PIDS+=($!)
echo -e "${GREEN}  Dashboard PID: ${PIDS[-1]}${NC}"
sleep 3

echo -e "\n${CYAN}========================================${NC}"
echo -e "${GREEN}  All services running!${NC}"
echo -e "${CYAN}========================================${NC}"
echo -e ""
echo -e "  Backend:    ${GREEN}http://localhost:8000${NC}"
echo -e "  Dashboard:  ${GREEN}http://localhost:5173${NC}"
echo -e "  Health:     ${GREEN}http://localhost:8000/health${NC}"
echo -e ""
echo -e "  Extension:  Load ${CYAN}quotex-alert-monitoring/extension/dist/${NC} in Chrome"
echo -e "              chrome://extensions/ -> Load unpacked"
echo -e ""
echo -e "  Logs:"
echo -e "    Backend:   tail -f /tmp/quotex-backend.log"
echo -e "    Dashboard: tail -f /tmp/quotex-dashboard.log"
echo -e ""
echo -e "  Press ${RED}Ctrl+C${NC} to stop all services"
echo -e ""

# Wait for any process to exit
wait
RUNSCRIPT

    chmod +x run.sh
    print_ok "Created run.sh (starts all services)"
}

# ---- Print summary ----
print_summary() {
    print_header "Setup Complete!"

    echo -e "  ${GREEN}All dependencies installed and configured.${NC}\n"
    echo -e "  ${CYAN}To start all services:${NC}"
    echo -e "    ${GREEN}./run.sh${NC}\n"
    echo -e "  ${CYAN}Or start individually:${NC}"
    echo -e "    ${YELLOW}# Terminal 1 - Backend${NC}"
    echo -e "    cd quotex-alert-monitoring/backend"
    echo -e "    source venv/bin/activate"
    echo -e "    uvicorn app.main:app --host 0.0.0.0 --port 8000\n"
    echo -e "    ${YELLOW}# Terminal 2 - Dashboard${NC}"
    echo -e "    cd quotex-alert-monitoring/dashboard"
    echo -e "    npm run dev\n"
    echo -e "  ${CYAN}Chrome Extension:${NC}"
    echo -e "    1. Open chrome://extensions/"
    echo -e "    2. Enable Developer mode"
    echo -e "    3. Load unpacked -> select ${YELLOW}quotex-alert-monitoring/extension/dist/${NC}"
    echo -e "    4. Open a Quotex trading page\n"
    echo -e "  ${CYAN}Then open:${NC}"
    echo -e "    Dashboard:  ${GREEN}http://localhost:5173${NC}"
    echo -e "    Backend:    ${GREEN}http://localhost:8000/health${NC}\n"
}

# ============================================================================
# MAIN
# ============================================================================

print_header "Quotex Alert Monitor - Setup"

# Move to project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

detect_os

if [ "$OS" = "unknown" ]; then
    print_err "Unsupported OS. Please install dependencies manually."
    exit 1
fi

if [ "$OS" = "windows" ]; then
    print_err "This script is for Linux/macOS. For Windows, run setup.ps1 instead."
    exit 1
fi

setup_python
setup_pip
setup_node
setup_mongodb
setup_backend
setup_dashboard
setup_extension
create_run_script
print_summary
