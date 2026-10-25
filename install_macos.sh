#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Active Assistant Installer for macOS
# Supports: macOS 10.15+ (Catalina) and later
###############################################################################

APP_NAME="Active Assistant"
APP_VERSION="2.0.0"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/Library/Application Support/Active Assistant"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/Applications"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Parse arguments
DEV=false
NO_VOSK=false
NO_STARTUP=false
BUILD_APP=false

for arg in "$@"; do
    case "$arg" in
        --dev) DEV=true ;;
        --no-vosk) NO_VOSK=true ;;
        --no-startup) NO_STARTUP=true ;;
        --build-app) BUILD_APP=true ;;
        --help|-h)
            echo "Usage: $0 [--dev] [--no-vosk] [--no-startup] [--build-app]"
            echo ""
            echo "Options:"
            echo "  --dev         Install in development mode (editable)"
            echo "  --no-vosk     Skip Vosk model download"
            echo "  --no-startup  Skip launchd service setup"
            echo "  --build-app   Build standalone .app bundle with PyInstaller"
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
echo "  Platform: macOS"
echo "==========================================="
echo ""

# -------------------------------------------------------
# 1. Check macOS version
# -------------------------------------------------------
macos_version=$(sw_vers -productVersion)
log_info "macOS version: $macos_version"

# Check Python 3.10+
if ! command -v python3 &>/dev/null; then
    log_error "Python 3 not found. Install from python.org or run: brew install python@3.10"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
log_info "Python version: $PYTHON_VERSION"

PY_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    log_error "Python 3.10+ required (found $PYTHON_VERSION)"
    exit 1
fi

# -------------------------------------------------------
# 2. Install system dependencies via Homebrew
# -------------------------------------------------------
log_info "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    log_info "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Add Homebrew to PATH for Apple Silicon
if [[ $(uname -m) == "arm64" ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

log_info "Installing system dependencies via Homebrew..."
brew install \
    python@3.11 \
    openssl \
    pkg-config \
    libffi \
    gtk+3 \
    libnotify \
    wget \
    curl \
    git \
    2>/dev/null || true

log_ok "System dependencies ready"

# -------------------------------------------------------
# 3. Install Python package
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
# 4. Download Vosk model
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
# 5. Create .env from template
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

CONFIG_PATH="${PROJECT_DIR}/config.yaml"
DEFAULT_CONFIG="${PROJECT_DIR}/config/default_config.yaml"
if [ ! -f "$CONFIG_PATH" ] && [ -f "$DEFAULT_CONFIG" ]; then
    cp "$DEFAULT_CONFIG" "$CONFIG_PATH"
    log_ok "Created config.yaml from defaults"
fi

# -------------------------------------------------------
# 6. Create wrapper script
# -------------------------------------------------------
log_info "Setting up command-line wrapper..."
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/active-assistant" << WRAPPER
#!/usr/bin/env bash
exec python3 -m active_assistant.main "\$@"
WRAPPER
chmod +x "$BIN_DIR/active-assistant"

log_ok "Wrapper installed at $BIN_DIR/active-assistant"

# -------------------------------------------------------
# 7. Create .app bundle (optional, for double-click launch)
# -------------------------------------------------------
if [ "$BUILD_APP" = true ]; then
    log_info "Building .app bundle with PyInstaller..."
    pip3 install pyinstaller --user
    pyinstaller "$PROJECT_DIR/active_assistant.spec"
    if [ -d "$PROJECT_DIR/dist/ActiveAssistant.app" ]; then
        log_ok "App bundle built at: $PROJECT_DIR/dist/ActiveAssistant.app"
        log_info "Copy to /Applications to install: cp -r dist/ActiveAssistant.app /Applications/"
    else
        log_error "App bundle build failed"
    fi
else
    # Create a simple .app wrapper for the Python entry point
    log_info "Creating lightweight .app wrapper..."
    APP_BUNDLE="${APP_DIR}/Active Assistant.app"
    mkdir -p "${APP_BUNDLE}/Contents/MacOS"
    mkdir -p "${APP_BUNDLE}/Contents/Resources"

    cat > "${APP_BUNDLE}/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Active Assistant</string>
    <key>CFBundleDisplayName</key>
    <string>Active Assistant</string>
    <key>CFBundleIdentifier</key>
    <string>com.activeassistant.app</string>
    <key>CFBundleVersion</key>
    <string>2.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>2.0.0</string>
    <key>CFBundleExecutable</key>
    <string>active-assistant-launcher</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.productivity</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>Active Assistant needs to control other applications for screen monitoring.</string>
    <key>NSScreenCaptureUsageDescription</key>
    <string>Active Assistant needs screen capture for vision monitoring.</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Active Assistant needs microphone access for voice input.</string>
</dict>
</plist>
PLIST

    cat > "${APP_BUNDLE}/Contents/MacOS/active-assistant-launcher" << LAUNCHER
#!/usr/bin/env bash
cd "${PROJECT_DIR}"
exec python3 -m active_assistant.main --ui
LAUNCHER
    chmod +x "${APP_BUNDLE}/Contents/MacOS/active-assistant-launcher"

    # Copy icon if available
    ICON_SRC="${PROJECT_DIR}/assets/icons/icon.icns"
    if [ -f "$ICON_SRC" ]; then
        cp "$ICON_SRC" "${APP_BUNDLE}/Contents/Resources/icon.icns"
    fi

    log_ok "App wrapper created at ${APP_BUNDLE}"
fi

# -------------------------------------------------------
# 8. Create launchd service (for background/tray mode)
# -------------------------------------------------------
if [ "$NO_STARTUP" = false ]; then
    log_info "Setting up launchd service..."
    LAUNCHD_DIR="${HOME}/Library/LaunchAgents"
    mkdir -p "$LAUNCHD_DIR"

    cat > "${LAUNCHD_DIR}/com.activeassistant.plist" << LAUNCHDEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.activeassistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>${BIN_DIR}/active-assistant</string>
        <string>--tray</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/active-assistant.out.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/active-assistant.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>
</dict>
</plist>
LAUNCHDEOF

    log_ok "Launchd service installed at ${LAUNCHD_DIR}/com.activeassistant.plist"
    log_info "To enable auto-start: launchctl load ${LAUNCHD_DIR}/com.activeassistant.plist"
else
    log_info "Skipping launchd service setup"
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
echo "  1. Edit ${PROJECT_DIR}/.env with your API keys"
echo "  2. Run: active-assistant          # Tray mode (background)"
echo "  3. Run: active-assistant --ui     # Full UI window"
echo "  4. Run: active-assistant --console # Console mode"
echo ""
echo "To launch from Spotlight: search for 'Active Assistant'"
echo "To enable auto-start: launchctl load ~/Library/LaunchAgents/com.activeassistant.plist"
echo ""
