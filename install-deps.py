#!/usr/bin/env python3
"""
Install dependencies for Find Evil!
Run this if setup.sh fails or packages are missing
"""
import subprocess
import sys
from pathlib import Path

def main():
    project_dir = Path(__file__).parent
    venv_dir = project_dir / "venv"
    requirements_file = project_dir / "requirements.txt"
    
    print("=" * 60)
    print("Find Evil! — Install Dependencies")
    print("=" * 60)
    
    # Check venv exists
    if not (venv_dir / "bin" / "python").exists():
        print("\n[ERROR] Virtual environment not found!")
        print("[INFO] Run: bash setup.sh")
        return 1
    
    python_exe = venv_dir / "bin" / "python"
    pip_exe = venv_dir / "bin" / "pip"
    
    # Upgrade pip
    print("\n[1/3] Upgrading pip...")
    try:
        subprocess.run(
            [str(pip_exe), "install", "--upgrade", "pip", "--break-system-packages", "--quiet"],
            check=False,
            capture_output=True
        )
        print("✓ pip upgraded")
    except Exception as e:
        print(f"✗ Failed to upgrade pip: {e}")
    
    # Install requirements
    print("\n[2/3] Installing requirements from requirements.txt...")
    try:
        result = subprocess.run(
            [str(pip_exe), "install", "-r", str(requirements_file), "--break-system-packages", "--quiet"],
            check=False,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ Requirements installed")
        else:
            print(f"⚠ Installation completed with warnings")
            if result.stderr:
                print(f"  stderr: {result.stderr[:200]}")
    except Exception as e:
        print(f"✗ Failed to install requirements: {e}")
        return 1
    
    # Verify
    print("\n[3/3] Verifying critical packages...")
    critical = ["mcp", "rich", "textual", "anthropic", "aiohttp"]
    optional = ["evtx", "pytsk3", "volatility3"]
    
    all_ok = True
    for pkg in critical:
        try:
            __import__(pkg)
            print(f"  ✓ {pkg}")
        except ImportError:
            print(f"  ✗ {pkg} - MISSING (CRITICAL)")
            all_ok = False
    
    print("\n[OPTIONAL PACKAGES]")
    for pkg in optional:
        try:
            __import__(pkg)
            print(f"  ✓ {pkg}")
        except ImportError:
            print(f"  ⚠ {pkg} - optional, some features disabled")
    
    if all_ok:
        print("\n" + "=" * 60)
        print("✅ All critical packages installed successfully!")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("❌ Some critical packages are missing!")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
