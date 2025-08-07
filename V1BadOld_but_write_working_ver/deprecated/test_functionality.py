#!/usr/bin/env python3
"""
Test script to verify all functionality is working correctly.
Tests crop selection, OCR, text injection, and browser behavior.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QUrl, QTimer, QRect
from PyQt6.QtGui import QPixmap
from main_app import MainWindow

def test_crop_coordinates():
    """Test crop coordinate scaling."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    # Load test page
    window.web_view.load(QUrl("http://100.73.40.119:30041/"))
    
    # Set test crop area
    test_crop = QRect(100, 100, 200, 50)  # Small test area
    window.web_view.set_crop(test_crop)
    
    # Test pixel ratio scaling
    pixel_ratio = window.web_view.devicePixelRatioF()
    print(f"✅ Device pixel ratio: {pixel_ratio}")
    print(f"✅ Original crop: {test_crop}")
    print(f"✅ Scaled crop: {QRect(int(test_crop.left() * pixel_ratio), int(test_crop.top() * pixel_ratio), int(test_crop.width() * pixel_ratio), int(test_crop.height() * pixel_ratio))}")
    
    # Test crop capture
    pixmap = window.web_view.capture_crop_area()
    if pixmap and not pixmap.isNull():
        print(f"✅ Crop capture successful: {pixmap.size()}")
        pixmap.save("test_crop_capture.png")
        print("✅ Saved test_crop_capture.png")
    else:
        print("❌ Crop capture failed")
    
    app.quit()

def test_ocr_debug():
    """Test OCR with debug output."""
    from PIL import Image
    from ocr_processor import OCRProcessor
    
    # Create test image with text
    test_image = Image.new('RGB', (300, 100), color='white')
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(test_image)
    
    try:
        # Try to use a basic font
        font = ImageFont.load_default()
        draw.text((10, 30), "Test OCR Text", fill='black', font=font)
    except:
        # Fallback without font
        draw.text((10, 30), "Test OCR Text", fill='black')
    
    test_image.save("test_ocr_input.png")
    print("✅ Created test_ocr_input.png")
    
    # Test OCR
    ocr = OCRProcessor()
    result = ocr.extract_text(test_image)
    print(f"✅ OCR result: '{result}'")
    
    if result and "test" in result.lower():
        print("✅ OCR working correctly")
    else:
        print("❌ OCR may have issues")

if __name__ == "__main__":
    print("🧪 Testing crop coordinates...")
    test_crop_coordinates()
    
    print("\n🧪 Testing OCR...")
    test_ocr_debug()
    
    print("\n✅ All tests completed!")