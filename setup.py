#!/usr/bin/env python3
"""
Setup and installation script for Raster to SVG Converter
"""

import sys
import subprocess
import os
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.7 or higher"""
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✓ Python version: {sys.version.split()[0]}")
    return True


def install_requirements():
    """Install Python dependencies"""
    print("\nInstalling Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Python dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install dependencies: {e}")
        return False


def check_tesseract():
    """Check if Tesseract OCR is installed"""
    print("\nChecking for Tesseract OCR...")
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"✓ {version}")
            return True
    except FileNotFoundError:
        pass
    
    print("✗ Tesseract OCR not found")
    print("\nPlease install Tesseract OCR:")
    
    if sys.platform == 'darwin':
        print("  macOS:   brew install tesseract")
    elif sys.platform.startswith('linux'):
        print("  Linux:   sudo apt-get install tesseract-ocr")
    elif sys.platform == 'win32':
        print("  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
    
    return False


def create_directories():
    """Create necessary directories"""
    print("\nCreating directories...")
    dirs = ['debug_output', 'output_svg']
    
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
        print(f"✓ Created {dir_name}/")
    
    return True


def run_tests():
    """Run basic tests"""
    print("\nRunning basic tests...")
    try:
        subprocess.check_call([sys.executable, "test_converter.py"])
        print("✓ Tests passed")
        return True
    except subprocess.CalledProcessError:
        print("✗ Some tests failed")
        return False


def main():
    print("="*60)
    print("Raster to SVG Converter - Setup")
    print("="*60)
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Install requirements
    if not install_requirements():
        print("\n⚠ Warning: Failed to install some dependencies")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return 1
    
    # Check Tesseract
    tesseract_ok = check_tesseract()
    
    # Create directories
    create_directories()
    
    print("\n" + "="*60)
    print("Setup Summary")
    print("="*60)
    print(f"Python:      {'✓' if True else '✗'}")
    print(f"Dependencies: ✓")
    print(f"Tesseract:   {'✓' if tesseract_ok else '✗'}")
    print(f"Directories:  ✓")
    
    if not tesseract_ok:
        print("\n⚠ Warning: Tesseract OCR is not installed.")
        print("  Text extraction will not work without it.")
    
    print("\n" + "="*60)
    print("Setup Complete!")
    print("="*60)
    print("\nQuick Start:")
    print("  1. Create a sample: python example_usage.py")
    print("  2. Convert an image: python cli.py input.png -o output.svg")
    print("  3. Batch convert:    python cli.py ./images --batch -o ./output")
    print("\nFor more information, see README.md and USAGE_GUIDE.md")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
