#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Active Assistant Installer for Linux
# Supports: Ubuntu/Debian, Fedora, Arch, openSUSE
###############################################################################

APP_NAME="Active Assistant"
APP_VERSION="2.0.0"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/share/active-assistant"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"
SYSTEMD_DIR="${HOME}/.config/systemd/user"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Parse arguments
DEV=false
NO_VOSK=false
NO_STARTUP=false
BUILD_EXE=false

for arg in "$@"; do
    case "$arg" in
        --dev) DEV=true ;;
        --no-vosk) NO_VOSK=true ;;
        --no-startup) NO_STARTUP=true ;;
        --build-exe) BUILD_EXE=true ;;
        --help|-h)
            echo "Usage: $0 [--dev] [--no-vosk] [--no-startup] [--build-exe]"
            echo ""
            echo "Options:"
            echo "  --dev         Install in development mode (editable)"
            echo "  --no-vosk     Skip Vosk model download"
            echo "  --no-startup  Skip systemd user service setup"
            echo "  --build-exe   Build standalone executable with PyInstaller"
            exit 0
            ;;
        *)
            log_error "Unknown option: $arg"
            exit 1
            ;;
    esac
done

echo "==========================================="
echo "  ${APP_NAME} Installer v${APP_VERSION}"
echo "  Platform: Linux"
echo "==========================================="
echo ""

# -------------------------------------------------------
# 1. Detect distribution and install system dependencies
# -------------------------------------------------------
log_info "Detecting Linux distribution..."

if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
    DISTRO_VERSION=$VERSION_ID
else
    log_error "Cannot detect Linux distribution (/etc/os-release missing)"
    exit 1
fi

log_info "Distribution: $DISTRO $DISTRO_VERSION"

# Check Python 3.10+
if ! command -v python3 &>/dev/null; then
    log_error "Python 3 not found. Please install Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
log_info "Python version: $PYTHON_VERSION"

# Verify Python >= 3.10
PY_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    log_error "Python 3.10+ required (found $PYTHON_VERSION)"
    exit 1
fi

# Install system dependencies based on distro
log_info "Installing system dependencies..."

install_deps_ubuntu() {
    sudo apt-get update -qq
    sudo apt-get install -y \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        libssl-dev \
        libffi-dev \
        pkg-config \
        libgtk-3-dev \
        libnotify-dev \
        libxcb1-dev \
        libxcb-render0-dev \
        libxcb-shape0-dev \
        libxcb-xfixes0-dev \
        wget \
        curl \
        git \
        xdg-utils
}

install_deps_fedora() {
    sudo dnf install -y \
        python3-pip \
        python3-devel \
        gcc \
        openssl-devel \
        libffi-devel \
        pkgconfig \
        gtk3-devel \
        libnotify-devel \
        libxcb-devel \
        wget \
        curl \
        git \
        xdg-utils
}

install_deps_arch() {
    sudo pacman -Syu --noconfirm \
        python-pip \
        python \
        base-devel \
        openssl \
        libffi \
        pkgconf \
        gtk3 \
        libnotify \
        libxcb \
        wget \
        curl \
        git \
        xdg-utils
}

install_deps_opensuse() {
    sudo zypper install -y \
        python3-pip \
        python3-devel \
        gcc \
        libopenssl-devel \
        libffi-devel \
        pkg-config \
        gtk3-devel \
        libnotify-devel \
        libxcb-devel \
        wget \
        curl \
        git \
        xdg-utils
}

case "$DISTRO" in
    ubuntu|debian|linuxmint|pop|neon) install_deps_ubuntu ;;
    fedora|rhel|centos|rocky|almalinux) install_deps_fedora ;;
    arch|manjaro|endeavouros) install_deps_arch ;;
    opensuse*|sles) install_deps_opensuse ;;
    *)
        log_warn "Unknown distribution: $DISTRO"
        log_warn "Attempting to install dependencies manually..."
        sudo apt-get update -qq 2>/dev/null && sudo apt-get install -y \
            python3-pip python3-venv python3-dev build-essential \
            libssl-dev libffi-dev pkg-config libgtk-3-dev libnotify-dev \
            libxcb1-dev libxcb-render0-dev libxcb-shape0-dev libxcb-xfixes0-dev \
            wget curl git xdg-utils 2>/dev/null || true
        ;;
esac

log_ok "System dependencies installed"

# -------------------------------------------------------
# 2. Install Python package
# -------------------------------------------------------
log_info "Installing Active Assistant Python package..."

cd "$PROJECT_DIR"

if [ "$DEV" = true ]; then
    pip3 install -e ".[dev]" --user
else
    pip3 install -e . --user
fi

log_ok "Python package installed"

# -------------------------------------------------------
# 3. Download Vosk model (for offline voice)
# -------------------------------------------------------
if [ "$NO_VOSK" = false ]; then
    log_info "Downloading Vosk speech recognition model..."
    if python3 scripts/download_vosk_model.py --model en-us; then
        log_ok "Vosk model downloaded"
    else
        log_warn "Vosk model download failed. Voice features may not work offline."
    fi
else
    log_info "Skipping Vosk model download"
fi

# -------------------------------------------------------
# 4. Create .env from template
# -------------------------------------------------------
log_info "Setting up configuration..."
ENV_PATH="${PROJECT_DIR}/.env"
ENV_EXAMPLE="${PROJECT_DIR}/.env.example"

if [ ! -f "$ENV_PATH" ] && [ -f "$ENV_EXAMPLE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_PATH"
    log_ok "Created .env from template (edit with your API keys)"
else
    log_info ".env already exists, skipping"
fi

# Copy default config if not present
CONFIG_PATH="${PROJECT_DIR}/config.yaml"
DEFAULT_CONFIG="${PROJECT_DIR}/config/default_config.yaml"
if [ ! -f "$CONFIG_PATH" ] && [ -f "$DEFAULT_CONFIG" ]; then
    cp "$DEFAULT_CONFIG" "$CONFIG_PATH"
    log_ok "Created config.yaml from defaults"
fi

# -------------------------------------------------------
# 5. Install .desktop file and systemd service
# -------------------------------------------------------
log_info "Setting up desktop integration..."

mkdir -p "$DESKTOP_DIR"
mkdir -p "$SYSTEMD_DIR"
mkdir -p "$BIN_DIR"

# Create wrapper script in ~/.local/bin
cat > "$BIN_DIR/active-assistant" << WRAPPER
#!/usr/bin/env bash
exec python3 -m active_assistant.main "\$@"
WRAPPER
chmod +x "$BIN_DIR/active-assistant"

# Create .desktop file
cat > "$DESKTOP_DIR/active-assistant.desktop" << DESKTOP
[Desktop Entry]
Name=Active Assistant
Comment=AI-powered desktop assistant with vision, voice, and plugins
Exec=python3 -m active_assistant.main --ui
Icon=active-assistant
Terminal=false
Type=Application
Categories=Office;Utility;AI;ArtificialIntelligence;
StartupNotify=true
Keywords=assistant;ai;voice;vision;automation;
X-GNOME-UsesNotifications=true
DESKTOP

# Try to install icon
if [ -f "$PROJECT_DIR/assets/icons/icon.png" ]; then
    mkdir -p "${HOME}/.local/share/icons/hicolor/256x256/apps"
    cp "$PROJECT_DIR/assets/icons/icon.png" \
        "${HOME}/.local/share/icons/hicolor/256x256/apps/active-assistant.png"
    log_ok "Icon installed"
fi

# Update desktop database
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

log_ok "Desktop integration installed"

# -------------------------------------------------------
# 6. Systemd user service (for background/tray mode)
# -------------------------------------------------------
if [ "$NO_STARTUP" = false ]; then
    log_info "Setting up systemd user service..."
    cat > "$SYSTEMD_DIR/active-assistant.service" << SERVICEEOF
[Unit]
Description=Active Assistant - AI Desktop Assistant
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart=${BIN_DIR}/active-assistant --tray
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
WorkingDirectory=${PROJECT_DIR}

[Install]
WantedBy=graphical-session.target
SERVICEEOF

    systemctl --user daemon-reload 2>/dev/null || true
    log_ok "Systemd user service installed at $SYSTEMD_DIR/active-assistant.service"
    log_info "To enable auto-start: systemctl --user enable --now active-assistant.service"
else
    log_info "Skipping systemd service setup"
fi

# -------------------------------------------------------
# 7. Build standalone executable (optional)
# -------------------------------------------------------
if [ "$BUILD_EXE" = true ]; then
    log_info "Building standalone executable with PyInstaller..."
    pip3 install pyinstaller --user
    pyinstaller "$PROJECT_DIR/active_assistant.spec"
    if [ -f "$PROJECT_DIR/dist/ActiveAssistant" ]; then
        log_ok "Executable built at: $PROJECT_DIR/dist/ActiveAssistant"
    else
        log_error "Executable build failed"
    fi
fi

# -------------------------------------------------------
# Done
# -------------------------------------------------------
echo ""
echo "==========================================="
echo "  Installation Complete!"
echo "==========================================="
echo ""
log_ok "Active Assistant v${APP_VERSION} is installed"
echo ""
echo "Next steps:"
echo "  1. Edit ~/.local/share/active-assistant/.env with your API keys"
echo "  2. Run: active-assistant          # Tray mode (background)"
echo "  3. Run: active-assistant --ui     # Full UI window"
echo "  4. Run: active-assistant --console # Console mode"
echo ""
echo "To launch from app menu: search for 'Active Assistant'"
echo "To enable auto-start: systemctl --user enable --now active-assistant.service"
echo ""
