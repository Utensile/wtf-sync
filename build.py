#!/usr/bin/env python3
"""
build.py  –  One-click builder for WTF Sync Tool
Run this on each OS you want to build for.

Requirements (run once):
    pip install pyinstaller
"""

import subprocess
import sys
import os
from pathlib import Path

HERE = Path(__file__).parent

def check_pyinstaller():
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__} found")
        return True
    except ImportError:
        return False

def install_pyinstaller():
    print("PyInstaller not found. Installing…")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        capture_output=False
    )
    return result.returncode == 0

def build():
    print(f"\n{'='*50}")
    print(f"  Building WTF Sync Tool for {sys.platform}")
    print(f"{'='*50}\n")

    if not check_pyinstaller():
        if not install_pyinstaller():
            print("\n✗ Failed to install PyInstaller.")
            print("  Try manually:  pip install pyinstaller")
            sys.exit(1)

    spec = HERE / "wow_wtf_sync.spec"
    if not spec.exists():
        print(f"✗ Spec file not found: {spec}")
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec), "--clean", "--noconfirm"],
        cwd=str(HERE)
    )

    if result.returncode != 0:
        print("\n✗ Build failed. Check the output above.")
        sys.exit(1)

    dist = HERE / "dist"
    print(f"\n{'='*50}")
    print("  ✓ Build complete!")
    print(f"  Output folder: {dist}")
    print()

    if sys.platform == "win32":
        exe = dist / "WTF Sync.exe"
        print(f"  Executable:  {exe}")
        print()
        print("  Place 'WTF Sync.exe' next to WoW.exe and double-click to run.")

    elif sys.platform == "darwin":
        app = dist / "WTF Sync.app"
        print(f"  App bundle:  {app}")
        print()
        print("  Place 'WTF Sync.app' next to WoW.exe (or anywhere) and open it.")
        print("  Note: first launch may need right-click → Open to bypass Gatekeeper.")

    else:
        binary = dist / "wtf-sync"
        print(f"  Binary:  {binary}")
        print()
        print("  Place 'wtf-sync' next to WoW and run:  ./wtf-sync")
        print("  (make executable first if needed:  chmod +x wtf-sync)")

    print(f"{'='*50}\n")

if __name__ == "__main__":
    build()
