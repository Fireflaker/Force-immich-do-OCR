#!/bin/bash
echo "Starting ImmichOCR_Modular v3.0.0..."
cd "$(dirname "$0")"

if [ -f "dist/ImmichOCR_Modular" ]; then
    echo "Launching application..."
    ./dist/ImmichOCR_Modular
else
    echo "ERROR: ImmichOCR_Modular not found in dist folder!"
    echo "Please run: python build_system.py"
    read -p "Press Enter to continue..."
fi
