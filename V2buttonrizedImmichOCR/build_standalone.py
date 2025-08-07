#!/usr/bin/env python3
"""
Build script for Immich OCR Standalone executable
Creates a self-contained executable with all dependencies.
"""

import sys
import subprocess
import os
from pathlib import Path

def check_pyinstaller():
    """Check if PyInstaller is available."""
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__} is available")
        return True
    except ImportError:
        print("✗ PyInstaller not found, installing...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
            print("✓ PyInstaller installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("✗ Failed to install PyInstaller")
            return False

def build_executable():
    """Build the standalone executable."""
    if not check_pyinstaller():
        return False
    
    print("\nBuilding Immich OCR Standalone executable...")
    
    # PyInstaller command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', 'ImmichOCR_Standalone',
        # CRITICAL: Exclude unnecessary modules to reduce executable size
        # Without excludes: 500MB+ executable with unused dependencies
        # With excludes: ~180MB focused executable
        '--exclude-module', 'PyQt5',  # Don't include Qt5 when using Qt6
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'scipy',
        '--exclude-module', 'pandas',
        '--exclude-module', 'IPython',
        '--exclude-module', 'tkinter',
        'working_originals/immich_ocr_standalone.py'
    ]
    
    try:
        subprocess.check_call(cmd)
        print("\n✓ Build completed successfully!")
        print("✓ Executable: dist/ImmichOCR_Standalone.exe")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed: {e}")
        return False

def test_executable():
    """Test the built executable."""
    exe_path = Path("dist/ImmichOCR_Standalone.exe")
    if exe_path.exists():
        print(f"\n✓ Executable exists: {exe_path}")
        print(f"✓ Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
        return True
    else:
        print(f"\n✗ Executable not found: {exe_path}")
        return False

def main():
    """Main build process."""
    print("Immich OCR Standalone - Build Script")
    print("=" * 40)
    
    # Build executable
    if build_executable():
        # Test executable
        if test_executable():
            print("\n🎉 Build process completed successfully!")
            print("\nTo run:")
            print("  ./dist/ImmichOCR_Standalone.exe")
        else:
            print("\n⚠️  Build completed but executable test failed")
    else:
        print("\n❌ Build process failed")
        sys.exit(1)

if __name__ == "__main__":
    main()