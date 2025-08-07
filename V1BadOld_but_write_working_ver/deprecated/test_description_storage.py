#!/usr/bin/env python3
"""
Test script to determine where Immich stores the Description field.

Usage:
1. Run this script to create a test image with description
2. Upload to Immich
3. Edit description in Immich GUI
4. Re-run script to check where the description is stored
"""

import subprocess
import os
from PIL import Image, ImageDraw, ImageFont
import sys

def create_test_image():
    """Create a simple test image with recognizable content"""
    img = Image.new('RGB', (800, 400), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a reasonable font
    try:
        font = ImageFont.truetype("arial.ttf", 36)
        small_font = ImageFont.truetype("arial.ttf", 24)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 36)
            small_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
    
    # Add test content
    draw.text((50, 50), "TEST SCREENSHOT", fill='black', font=font)
    draw.text((50, 120), "Login Form", fill='blue', font=small_font)
    draw.text((50, 160), "Username: testuser@example.com", fill='black', font=small_font)
    draw.text((50, 200), "Password: ********", fill='black', font=small_font)
    draw.text((50, 240), "Remember me checkbox", fill='gray', font=small_font)
    draw.text((50, 280), "Submit Button", fill='green', font=small_font)
    
    # Draw some rectangles to simulate form elements
    draw.rectangle([300, 155, 600, 185], outline='black', width=2)  # Username field
    draw.rectangle([300, 195, 600, 225], outline='black', width=2)  # Password field
    draw.rectangle([300, 275, 400, 305], fill='green', outline='black')  # Submit button
    
    return img

def add_description_to_image(image_path, description_text):
    """Add description to image metadata using ExifTool"""
    print(f"Adding description to {image_path}...")
    
    # Test multiple description fields
    cmd = [
        'exiftool',
        f'-EXIF:ImageDescription={description_text}',
        f'-IPTC:Caption-Abstract={description_text}', 
        f'-XMP-dc:Description={description_text}',
        '-overwrite_original',
        image_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Successfully added description to metadata")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error adding metadata: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ ExifTool not found. Please install exiftool first.")
        print("Install with: brew install exiftool (Mac) or apt install libimage-exiftool-perl (Ubuntu)")
        return False

def read_metadata(image_path):
    """Read all metadata from image to see what's stored where"""
    print(f"\n📖 Reading metadata from {image_path}...")
    
    cmd = [
        'exiftool',
        '-EXIF:ImageDescription',
        '-IPTC:Caption-Abstract', 
        '-XMP-dc:Description',
        '-json',
        image_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        metadata = json.loads(result.stdout)[0]
        
        print("\n📋 Current metadata:")
        print(f"EXIF ImageDescription: {metadata.get('ImageDescription', 'NOT SET')}")
        print(f"IPTC Caption-Abstract: {metadata.get('Caption-Abstract', 'NOT SET')}")
        print(f"XMP-dc Description: {metadata.get('Description', 'NOT SET')}")
        
        return metadata
    except Exception as e:
        print(f"❌ Error reading metadata: {e}")
        return None

def main():
    test_image_path = "test_screenshot_description.png"
    
    print("🔬 Testing Immich Description Storage")
    print("=" * 50)
    
    # Step 1: Create test image
    print("1️⃣ Creating test screenshot image...")
    img = create_test_image()
    img.save(test_image_path)
    print(f"✅ Created {test_image_path}")
    
    # Step 2: Add initial description
    initial_description = "OCR: Login form with username testuser@example.com, password field, and submit button"
    
    if add_description_to_image(test_image_path, initial_description):
        read_metadata(test_image_path)
    
    print("\n" + "=" * 50)
    print("📝 NEXT STEPS:")
    print("1. Upload test_screenshot_description.png to Immich")
    print("2. Check if the description appears in Immich")
    print("3. Edit the description in Immich GUI to: 'EDITED IN IMMICH'")
    print("4. Download the image from Immich")
    print("5. Run this script again to see where Immich stored the edit")
    print("6. Or check the metadata of the downloaded file manually")
    
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        print("\n🔍 CHECKING DOWNLOADED FILE...")
        downloaded_file = input("Enter path to downloaded file: ")
        if os.path.exists(downloaded_file):
            read_metadata(downloaded_file)

if __name__ == "__main__":
    main() 