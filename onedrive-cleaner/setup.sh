#!/usr/bin/env bash
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${GREEN}%s${NC}\n" "$1"; }
warn()  { printf "${YELLOW}%s${NC}\n" "$1"; }
error() { printf "${RED}%s${NC}\n" "$1"; }

info "========================================"
info "  OneDrive Screenshot Cleaner — Setup"
info "========================================"
echo ""

if [[ "$OSTYPE" != "darwin"* ]]; then
    error "This setup script is designed for macOS only."
    exit 1
fi

info "[1/6] Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    warn "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    info "Homebrew installed."
else
    info "Homebrew found at $(command -v brew)"
fi

info "[2/6] Checking Python 3.11+..."
PYTHON=""
for candidate in python3 python3.11 python3.12 python3.13; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        major="${ver%.*}"
        minor="${ver#*.}"
        if [[ "$major" -ge 3 && "$minor" -ge 11 ]] 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    warn "Python 3.11+ not found. Installing via Homebrew..."
    brew install python
    PYTHON="python3"
fi
info "Using $($PYTHON --version)"

info "[3/6] Checking Tesseract OCR..."
if ! command -v tesseract &>/dev/null; then
    warn "Tesseract not found. Installing via Homebrew..."
    brew install tesseract
fi
info "Tesseract: $(tesseract --version 2>&1 | head -1)"

VENV_DIR="$APP_DIR/venv"
if [[ ! -d "$VENV_DIR" ]]; then
    info "[4/6] Creating virtual environment..."
    $PYTHON -m venv "$VENV_DIR"
else
    info "[4/6] Virtual environment already exists."
fi

info "[5/6] Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
"$VENV_DIR/bin/pip" install --quiet -e "$APP_DIR"
info "Dependencies installed."

info "[6/6] Checking .env configuration..."
if [[ ! -f "$APP_DIR/.env" ]]; then
    touch "$APP_DIR/.env"
fi

source "$APP_DIR/.env" 2>/dev/null || true

if [[ -z "$CLIENT_ID" || "$CLIENT_ID" == "YOUR_CLIENT_ID" || \
      -z "$TENANT_ID" || "$TENANT_ID" == "YOUR_TENANT_ID" ]]; then
    warn ""
    warn "⚠  Microsoft Azure credentials not configured."
    warn ""
    printf "Enter your Azure CLIENT_ID: "
    read -r input_client
    printf "Enter your TENANT_ID (or 'consumers' for personal accounts): "
    read -r input_tenant

    cat > "$APP_DIR/.env" << EOF
CLIENT_ID=${input_client}
TENANT_ID=${input_tenant:-consumers}
EOF
    info ".env file created."
else
    info "CLIENT_ID and TENANT_ID are set."
fi

echo ""
info "========================================"
info "  Setup complete! Launching app..."
info "========================================"
echo ""

"$VENV_DIR/bin/streamlit" run "$APP_DIR/app.py"
