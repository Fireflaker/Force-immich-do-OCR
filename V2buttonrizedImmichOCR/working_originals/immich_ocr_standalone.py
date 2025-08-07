#!/usr/bin/env python3
"""
Immich OCR Standalone - Self-contained OCR automation tool
Automatically checks and installs dependencies, then provides OCR functionality.
"""

import sys
import subprocess
import importlib.util
import os
from pathlib import Path

def check_and_install_dependencies():
    """Check for required packages and install if missing."""
    required_packages = {
        'PyQt6': 'PyQt6>=6.4.0',
        'PyQt6.QtWebEngineWidgets': 'PyQt6-WebEngine>=6.4.0', 
        'PIL': 'Pillow>=9.0.0',
        'pytesseract': 'pytesseract>=0.3.10'
    }
    
    missing_packages = []
    
    for package, pip_name in required_packages.items():
        try:
            if package == 'PyQt6.QtWebEngineWidgets':
                import PyQt6.QtWebEngineWidgets
            elif package == 'PIL':
                import PIL
            else:
                __import__(package)
            print(f"✓ {package} is available")
        except ImportError:
            print(f"✗ {package} not found")
            missing_packages.append(pip_name)
    
    if missing_packages:
        print(f"\nInstalling missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
            print("✓ All dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install dependencies: {e}")
            sys.exit(1)
    else:
        print("✓ All dependencies are available")

def check_tesseract():
    """Check if Tesseract OCR is installed."""
    try:
        subprocess.run(['tesseract', '--version'], capture_output=True, check=True)
        print("✓ Tesseract OCR is available")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ Tesseract OCR not found")
        print("  Download from: https://github.com/UB-Mannheim/tesseract/wiki")
        return False

def main():
    """Main application entry point with dependency checking."""
    print("Immich OCR Standalone - Dependency Check")
    print("=" * 40)
    
    # Check and install Python dependencies
    check_and_install_dependencies()
    
    # Check Tesseract
    tesseract_available = check_tesseract()
    
    print("\n" + "=" * 40)
    print("Starting Immich OCR Browser...")
    
    # Import and run the main application
    try:
        # Import after dependency check
        from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLineEdit, QLabel, QMessageBox, QRubberBand, QSplitter
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
        from PyQt6.QtCore import Qt, QRect, QPoint, QSize, QEvent, QUrl, pyqtSignal, QTimer, QThread
        from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap
        from PIL import Image, ImageEnhance, ImageFilter
        import pytesseract
        
        class SimpleOCRApp(QMainWindow):
            def __init__(self):
                super().__init__()
                self.setWindowTitle("Immich OCR Standalone")
                self.setGeometry(100, 100, 1200, 800)
                
                # Setup UI
                central_widget = QWidget()
                self.setCentralWidget(central_widget)
                layout = QVBoxLayout(central_widget)
                
                # URL input
                url_layout = QHBoxLayout()
                url_layout.addWidget(QLabel("URL:"))
                self.url_input = QLineEdit("http://100.73.40.119:30041/")
                url_layout.addWidget(self.url_input)
                load_btn = QPushButton("Load")
                load_btn.clicked.connect(self.load_url)
                url_layout.addWidget(load_btn)
                layout.addLayout(url_layout)
                
                # Controls
                controls = QHBoxLayout()
                self.crop_btn = QPushButton("Select Crop Area")
                self.crop_btn.clicked.connect(self.start_crop)
                self.ocr_btn = QPushButton("Run OCR")
                self.ocr_btn.clicked.connect(self.run_ocr)
                self.ocr_btn.setEnabled(False)
                controls.addWidget(self.crop_btn)
                controls.addWidget(self.ocr_btn)
                controls.addStretch()
                layout.addLayout(controls)
                
                # Web view
                self.web_view = QWebEngineView()
                layout.addWidget(self.web_view)
                
                # Status
                self.status = QLabel("Ready - Load URL to begin")
                layout.addWidget(self.status)
                
                # Crop rectangle
                self.crop_rect = None
                
                if not tesseract_available:
                    QMessageBox.warning(self, "Tesseract Missing", 
                                      "Tesseract OCR not found. OCR functionality will be limited.\n"
                                      "Download from: https://github.com/UB-Mannheim/tesseract/wiki")
            
            def load_url(self):
                url = self.url_input.text()
                self.web_view.load(QUrl(url))
                self.status.setText(f"Loading: {url}")
                
            def start_crop(self):
                self.status.setText("Click and drag to select crop area")
                # Simple crop - just enable OCR for demo
                self.crop_rect = QRect(100, 100, 200, 50)
                self.ocr_btn.setEnabled(True)
                self.status.setText("Crop area selected (demo)")
                
            def run_ocr(self):
                if not tesseract_available:
                    QMessageBox.information(self, "OCR Demo", "Tesseract not available - this is a demo")
                    return
                    
                try:
                    # Capture web view
                    pixmap = self.web_view.grab()
                    
                    # Convert to PIL Image
                    image = pixmap.toImage()
                    w, h = image.width(), image.height()
                    ptr = image.bits()
                    ptr.setsize(h * w * 4)
                    arr = bytes(ptr)
                    pil_image = Image.frombytes('RGBA', (w, h), arr)
                    
                    # Simple OCR
                    text = pytesseract.image_to_string(pil_image)
                    
                    if text.strip():
                        QMessageBox.information(self, "OCR Result", f"Extracted text:\n{text}")
                        self.status.setText("OCR completed successfully")
                    else:
                        QMessageBox.information(self, "OCR Result", "No text detected")
                        self.status.setText("OCR completed - no text found")
                        
                except Exception as e:
                    QMessageBox.critical(self, "OCR Error", f"OCR failed: {str(e)}")
                    self.status.setText("OCR failed")
        
        # Run application
        app = QApplication(sys.argv)
        app.setApplicationName("Immich OCR Standalone")
        
        window = SimpleOCRApp()
        window.show()
        
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()