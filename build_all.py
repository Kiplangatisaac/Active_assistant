#!/usr/bin/env python3
"""
Build orchestrator for Active Assistant.
Builds install packages for Windows, Linux, and macOS.

Usage:
    python build_all.py --platform windows
    python build_all.py --platform linux
    python build_all.py --platform macos
    python build_all.py --platform all
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and print output."""
    print(f"[RUN] {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check)


def ensure_pyinstaller() -> None:
    """Ensure PyInstaller is installed."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[INFO] Installing PyInstaller...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0.0"])


def clean_build() -> None:
    """Clean previous build artifacts."""
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            print(f"[CLEAN] Removing {d}")
            shutil.rmtree(d)


def build_windows() -> None:
    """Build Windows executable (.exe)."""
    if not IS_WINDOWS:
        print("[WARN] Windows builds require Windows host. Skipping.")
        return

    print("\n=== Building Windows Package ===")
    ensure_pyinstaller()
    clean_build()

    spec = PROJECT_DIR / "active_assistant.spec"
    run([sys.executable, "-m", "PyInstaller", str(spec), "--clean"])

    exe_path = DIST_DIR / "ActiveAssistant.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n[OK] Windows executable: {exe_path} ({size_mb:.1f} MB)")
    else:
        print("\n[ERROR] Windows executable not found!")


def build_linux() -> None:
    """Build Linux executable and package."""
    print("\n=== Building Linux Package ===")
    ensure_pyinstaller()
    clean_build()

    spec = PROJECT_DIR / "active_assistant.spec"
    run([sys.executable, "-m", "PyInstaller", str(spec), "--clean"])

    exe_path = DIST_DIR / "ActiveAssistant"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n[OK] Linux executable: {exe_path} ({size_mb:.1f} MB)")
    else:
        print("\n[ERROR] Linux executable not found!")

    # Create .tar.gz package
    package_dir = DIST_DIR / "active-assistant-linux"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    # Copy executable
    if exe_path.exists():
        shutil.copy2(exe_path, package_dir / "ActiveAssistant")
        os.chmod(package_dir / "ActiveAssistant", 0o755)

    # Copy assets
    assets_src = PROJECT_DIR / "assets"
    if assets_src.exists():
        shutil.copytree(assets_src, package_dir / "assets")

    # Copy config
    config_src = PROJECT_DIR / "config" / "default_config.yaml"
    if config_src.exists():
        shutil.copy2(config_src, package_dir / "default_config.yaml")

    # Copy .env.example
    env_example = PROJECT_DIR / ".env.example"
    if env_example.exists():
        shutil.copy2(env_example, package_dir / ".env.example")

    # Copy install script
    install_sh = PROJECT_DIR / "install.sh"
    if install_sh.exists():
        shutil.copy2(install_sh, package_dir / "install.sh")
        os.chmod(package_dir / "install.sh", 0o755)

    # Copy README
    readme = PROJECT_DIR / "README.md"
    if readme.exists():
        shutil.copy2(readme, package_dir / "README.md")

    # Create tarball
    tarball = DIST_DIR / "active-assistant-linux.tar.gz"
    if tarball.exists():
        tarball.unlink()
    shutil.make_archive(str(tarball.with_suffix("")), "gztar", root_dir=DIST_DIR, base_dir="active-assistant-linux")
    # Clean up the temp dir
    shutil.rmtree(package_dir)

    if tarball.exists():
        size_mb = tarball.stat().st_size / (1024 * 1024)
        print(f"\n[OK] Linux package: {tarball} ({size_mb:.1f} MB)")


def build_macos() -> None:
    """Build macOS .app bundle."""
    if not IS_MACOS:
        print("[WARN] macOS builds require macOS host. Skipping.")
        return

    print("\n=== Building macOS Package ===")
    ensure_pyinstaller()
    clean_build()

    spec = PROJECT_DIR / "active_assistant.spec"
    run([sys.executable, "-m", "PyInstaller", str(spec), "--clean"])

    app_path = DIST_DIR / "ActiveAssistant.app"
    if app_path.exists():
        # Calculate size
        total_size = sum(f.stat().st_size for f in app_path.rglob("*") if f.is_file())
        size_mb = total_size / (1024 * 1024)
        print(f"\n[OK] macOS app bundle: {app_path} ({size_mb:.1f} MB)")
        print(f"       To install: cp -r {app_path} /Applications/")
    else:
        exe_path = DIST_DIR / "ActiveAssistant"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\n[OK] macOS executable: {exe_path} ({size_mb:.1f} MB)")
        else:
            print("\n[ERROR] macOS build artifact not found!")


def build_all() -> None:
    """Build for all supported platforms (platform-specific)."""
    if IS_WINDOWS:
        build_windows()
    elif IS_MACOS:
        build_macos()
    elif IS_LINUX:
        build_linux()
    else:
        print(f"[ERROR] Unsupported platform: {sys.platform}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Active Assistant install packages"
    )
    parser.add_argument(
        "--platform",
        choices=["windows", "linux", "macos", "all"],
        default="all",
        help="Target platform (default: all for current platform)",
    )
    args = parser.parse_args()

    print(f"Active Assistant Build Orchestrator v2.0.0")
    print(f"Host platform: {sys.platform}")
    print(f"Project dir: {PROJECT_DIR}")
    print()

    if args.platform == "windows":
        build_windows()
    elif args.platform == "linux":
        build_linux()
    elif args.platform == "macos":
        build_macos()
    elif args.platform == "all":
        build_all()


if __name__ == "__main__":
    main()
