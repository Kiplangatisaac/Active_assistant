<#
.SYNOPSIS
    Install Active Assistant on Windows

.DESCRIPTION
    This script installs Active Assistant with all dependencies,
    downloads required models, and optionally configures Windows startup.
#>

param(
    [switch]$Dev,
    [switch]$NoVosk,
    [switch]$NoStartup,
    [switch]$BuildExe
)

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  Active Assistant Installer" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python not found. Please install Python 3.10+ from python.org"
    exit 1
}

Write-Host "Found Python: $($python.Version)" -ForegroundColor Green

# Check if in project directory
$projectDir = $PSScriptRoot
if (-not (Test-Path "$projectDir\pyproject.toml")) {
    Write-Error "Not in Active Assistant project directory"
    exit 1
}

# Install package
Write-Host "`n[1/5] Installing package..." -ForegroundColor Yellow
if ($Dev) {
    pip install -e ".[dev]"
} else {
    pip install -e .
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Package installation failed"
    exit 1
}

# Download Vosk model
if (-not $NoVosk) {
    Write-Host "`n[2/5] Downloading Vosk model..." -ForegroundColor Yellow
    python "$projectDir\scripts\download_vosk_model.py" --model en-us
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Vosk model download failed. Voice features may not work."
    }
} else {
    Write-Host "`n[2/5] Skipping Vosk model download" -ForegroundColor Yellow
}

# Create .env if not exists
Write-Host "`n[3/5] Setting up configuration..." -ForegroundColor Yellow
$envPath = "$projectDir\.env"
$envExample = "$projectDir\.env.example"
if (-not (Test-Path $envPath) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envPath
    Write-Host "Created .env from template. Please edit with your API keys." -ForegroundColor Yellow
}

# Create config.yaml if not exists
$configPath = "$projectDir\config.yaml"
$defaultConfig = "$projectDir\config\default_config.yaml"
if (-not (Test-Path $configPath) -and (Test-Path $defaultConfig)) {
    Copy-Item $defaultConfig $configPath
    Write-Host "Created config.yaml from defaults" -ForegroundColor Green
}

# Configure Windows Startup
if (-not $NoStartup) {
    Write-Host "`n[4/5] Configuring Windows Startup..." -ForegroundColor Yellow
    $result = python -c "
from active_assistant.startup.manager import startup_manager
import asyncio
asyncio.run(startup_manager.configure())
print('Startup configured' if startup_manager.is_startup_enabled() else 'Startup not enabled')
"
    Write-Host $result -ForegroundColor Green
} else {
    Write-Host "`n[4/5] Skipping startup configuration" -ForegroundColor Yellow
}

# Build executable
if ($BuildExe) {
    Write-Host "`n[5/5] Building executable..." -ForegroundColor Yellow
    pip install pyinstaller
    pyinstaller "$projectDir\active_assistant.spec"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Executable built at: $projectDir\dist\ActiveAssistant.exe" -ForegroundColor Green
    } else {
        Write-Error "Executable build failed"
    }
}

Write-Host "`n===========================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1. Edit .env with your API keys"
Write-Host "  2. Run 'active-assistant' to start"
Write-Host "  3. Run 'active-assistant-ui' for the full interface"
Write-Host ""
Write-Host "Commands:" -ForegroundColor Green
Write-Host "  active-assistant        # System tray mode"
Write-Host "  active-assistant --ui   # Full UI window"
Write-Host "  active-assistant --console  # Console mode"
Write-Host "  active-assistant-setup  # Re-run setup"