# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Active Assistant
# Cross-platform: Windows, Linux, macOS
# Build with: pyinstaller active_assistant.spec

import sys
import os
import platform
from pathlib import Path

# Get the directory containing this spec file
# Note: __file__ is not available in PyInstaller spec execution context,
# so we use Path.cwd() instead
SPEC_DIR = Path.cwd()
MAIN_SCRIPT = SPEC_DIR / "src" / "active_assistant" / "main.py"

# Icon file (platform-specific)
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

ICON_FILE = SPEC_DIR / "assets" / "icons" / "icon.ico"
if IS_MACOS:
    ICON_FILE = SPEC_DIR / "assets" / "icons" / "icon.icns"
elif IS_LINUX:
    ICON_FILE = SPEC_DIR / "assets" / "icons" / "icon.png"

block_cipher = None

# --- Analysis ---
a = Analysis(
    [str(MAIN_SCRIPT)],
    pathex=[str(SPEC_DIR / "src")],
    binaries=[],
    datas=[
        # Include config files
        (str(SPEC_DIR / "config" / "default_config.yaml"), "config"),
        # Include assets
        (str(SPEC_DIR / "assets"), "assets"),
        # Include .env.example as template
        (str(SPEC_DIR / ".env.example"), "."),
    ],
    hiddenimports=[
        # Core dependencies
        "groq",
        "mss",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageTk",
        "plyer",
        "pystray",
        # Standard library modules
        "shlex",
        "queue",
        "threading",
        "json",
        "base64",
        "io",
        "pathlib",
        "subprocess",
        "shutil",
        "logging",
        "datetime",
        "ctypes",
        "ctypes.util",
        "asyncio",
        "concurrent.futures",
        "collections.abc",
        "typing",
        "dataclasses",
        "enum",
        "uuid",
        "hashlib",
        "hmac",
        "secrets",
        "string",
        "re",
        "textwrap",
        "functools",
        "itertools",
        "operator",
        "math",
        "statistics",
        "decimal",
        "fractions",
        "random",
        "time",
        "calendar",
        "zoneinfo",
        # AI Providers
        "openai",
        "anthropic",
        "ollama",
        # Voice
        "speech_recognition",
        "pyttsx3",
        "vosk",
        "sounddevice",
        "pyaudio",
        # Web
        "aiohttp",
        "brave_search",
        "requests",
        "bs4",
        "lxml",
        # UI
        "customtkinter",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
        "tkinter.colorchooser",
        "tkinter.font",
        "tkinter.scrolledtext",
        # System
        "psutil",
        "watchdog",
        "dotenv",
        "pydantic",
        "pydantic_settings",
        "yaml",
        "toml",
        "rich",
        "loguru",
        # Plugin
        "pluggy",
        "importlib_metadata",
        # SSL/Crypto (needed by anyio/httpx)
        "ssl",
        "_ssl",
        "certifi",
        "anyio",
        "anyio._core._sockets",
        "anyio._backends._asyncio",
        "httpx",
        "httpcore",
        "pydantic_core",
        # Active Assistant modules
        "active_assistant",
        "active_assistant.core",
        "active_assistant.core.config",
        "active_assistant.core.state",
        "active_assistant.core.providers",
        "active_assistant.core.monitor",
        "active_assistant.core.logging",
        "active_assistant.tools",
        "active_assistant.tools.base",
        "active_assistant.agents",
        "active_assistant.agents.manager",
        "active_assistant.plugins",
        "active_assistant.plugins.manager",
        "active_assistant.voice",
        "active_assistant.voice.assistant",
        "active_assistant.web",
        "active_assistant.web.crawler",
        "active_assistant.web.stream",
        "active_assistant.startup",
        "active_assistant.startup.manager",
        "active_assistant.ui",
        "active_assistant.ui.main_window",
        "active_assistant.tray",
        "active_assistant.main",
        "active_assistant.mcp",
        "active_assistant.mcp.server",
        "active_assistant.mcp.client",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude large/unused packages to reduce size
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "sklearn",
        "torch",
        "tensorflow",
        "jupyter",
        "IPython",
        "notebook",
        "pytest",
        "black",
        "ruff",
        "mypy",
        "sphinx",
        "docutils",
        "setuptools",
        "pip",
        "wheel",
        "pkg_resources",
        "zipp",
        "jaraco",
        "more_itertools",
        "distlib",
        "platformdirs",
        "filelock",
        "virtualenv",
        "tkinter.test",
        "tkinter.test.support",
        "lib2to3",
        "ensurepip",
        "distutils",
        "configparser",
        "argparse",
        "html",
        "xmlrpc",
        "wave",
        "colorsys",
        "crypt",
        "dbm",
        "gdbm",
        "spwd",
        "syslog",
        "nis",
        "ossaudiodev",
        "sunau",
        "aifc",
        "audioop",
        "msilib",
    ]
    + (["msvcrt", "nt", "win32api", "win32con", "win32gui", "win32process", "pywintypes", "winshell", "pythoncom", "win32com", "win32com.client"] if not IS_WINDOWS else []),
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out None entries from hiddenimports
a.hiddenimports = [h for h in a.hiddenimports if h is not None]

# Platform-specific binaries
if IS_WINDOWS:
    # Add SSL DLLs on Windows
    import glob
    python_dlls = Path(sys.base_prefix) / "DLLs"
    ssl_dlls = (
        list(python_dlls.glob("_ssl*.pyd"))
        + list(python_dlls.glob("_hashlib*.pyd"))
        + list(python_dlls.glob("libssl*.dll"))
        + list(python_dlls.glob("libcrypto*.dll"))
    )
    for dll in ssl_dlls:
        a.binaries.append((dll.name, str(dll), "BINARY"))

    # Filter out unwanted system DLLs on Windows
    system_dlls = {
        "api-ms-win", "ucrtbase", "vcruntime", "msvcp", "kernel32", "user32",
        "gdi32", "advapi32", "shell32", "ole32", "oleaut32", "comdlg32",
        "version", "ws2_32", "winhttp", "wininet", "crypt32", "bcrypt",
        "ncrypt", "secur32", "sspicli", "cryptsp", "rsaenh", "dpapi",
        "cryptdll",
    }
    a.binaries = [
        (name, path, typ)
        for name, path, typ in a.binaries
        if not any(excl in name.lower() for excl in system_dlls)
    ]

# --- PYZ (Python archive) ---
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- EXE / App Bundle ---
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ActiveAssistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=not IS_MACOS,  # macOS uses windowed (app bundle)
    disable_windowed_traceback=False,
    argv_emulation=IS_MACOS,  # macOS argv emulation
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_FILE) if ICON_FILE.exists() else None,
    version_file=str(SPEC_DIR / "version_info.txt")
    if (IS_WINDOWS and (SPEC_DIR / "version_info.txt").exists())
    else None,
)

# --- App Bundle for macOS ---
if IS_MACOS:
    from PyInstaller.utils.cliutils.app_name import get_app_name
    from PyInstaller.building.osx import BUNDLE

    app = BUNDLE(
        exe,
        name="ActiveAssistant.app",
        icon=str(ICON_FILE) if ICON_FILE.exists() else None,
        bundle_identifier="com.activeassistant.app",
        info_plist={
            "CFBundleName": "Active Assistant",
            "CFBundleDisplayName": "Active Assistant",
            "CFBundleIdentifier": "com.activeassistant.app",
            "CFBundleVersion": "2.0.0",
            "CFBundleShortVersionString": "2.0.0",
            "NSHighResolutionCapable": "True",
            "LSApplicationCategoryType": "public.app-category.productivity",
        },
    )

# --- Optional: Create a one-folder build for easier debugging ---
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=True,
#     upx=True,
#     upx_exclude=[],
#     name="ActiveAssistant",
# )
