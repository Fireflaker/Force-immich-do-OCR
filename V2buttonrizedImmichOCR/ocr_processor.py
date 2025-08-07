#!/usr/bin/env python3
"""
OCR Processing module for Immich OCR Browser
Handles image preprocessing and text extraction.

CRITICAL LESSON: NO ARTIFICIAL UPSCALING!
- Upscaling creates fake data and hurts OCR accuracy
- Use proper preprocessing: denoising, conservative contrast, subtle sharpening
- High DPI captures are already large enough - don't artificially enlarge them
"""

import io
import platform
import shutil
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from typing import Optional, Tuple
from config import config


class OCRProcessor:
    """Handles OCR processing with optimized image preprocessing."""
    
    def __init__(self):
        self.config = config.ocr
        
        # CRITICAL: Ensure Tesseract is found on Windows (same as working version)
        # This fixes the "Tesseract not installed" error when it's actually installed
        if platform.system() == "Windows" and shutil.which("tesseract") is None:
            default_tess = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if shutil.which(default_tess):
                pytesseract.pytesseract.tesseract_cmd = default_tess
    
    def preprocess_image(self, pil_img: Image.Image) -> Image.Image:
        """
        Optimizes image for OCR without artificial upscaling.
        
        NEVER UPSCALE AGAIN: Creates artifacts that hurt OCR.
        Instead: Gentle denoising + conservative contrast + subtle sharpening.
        
        CRITICAL LESSON: Artificial upscaling hurts accuracy
        - Creates fake pixels that confuse OCR algorithms
        - High-DPI captures are already large enough
        - Real enhancement comes from proper preprocessing, not size
        
        Args:
            pil_img: Input PIL Image
            
        Returns:
            Preprocessed PIL Image optimized for OCR
        """
        # Convert to grayscale first - improves OCR accuracy
        gray_img = pil_img.convert("L")
        
        # Apply very mild Gaussian blur to reduce noise without losing text detail
        # Radius of 0.3 is subtle and helps with aliasing/noise
        denoised = gray_img.filter(ImageFilter.GaussianBlur(radius=0.3))
        
        # Conservative contrast enhancement - avoids creating artifacts
        enhancer = ImageEnhance.Contrast(denoised)
        contrast_img = enhancer.enhance(1.2)  # Conservative enhancement
        
        # Apply very mild sharpening to help with text edges
        # This helps with text edges without creating artifacts
        sharpener = ImageFilter.UnsharpMask(radius=0.5, percent=100, threshold=2)
        final_img = contrast_img.filter(sharpener)
        
        return final_img
    
    def extract_text(self, pil_img: Image.Image) -> str:
        """
        Extract text from preprocessed image using Tesseract.
        
        Args:
            pil_img: Preprocessed PIL Image
            
        Returns:
            Extracted text string
        """
        try:
            # Preprocess the image
            processed_img = self.preprocess_image(pil_img)
            
            # Run OCR with configured settings
            raw_text = pytesseract.image_to_string(
                processed_img, 
                config=self.config.tesseract_config
            ).strip()
            
            # Apply Reply to [text] pattern filtering from quick_ocr_test.py
            return self._filter_text_with_reply_pattern(raw_text)
            
        except Exception as e:
            error_msg = str(e)
            if "tesseract is not installed" in error_msg or "tesseract: command not found" in error_msg:
                return "Tesseract OCR not installed"
            return f"OCR Error: {error_msg}"
    
    def _filter_text_with_reply_pattern(self, raw_text: str) -> str:
        """
        Filter OCR text with Reply to [text] pattern extraction - EXACT COPY from quick_ocr_test.py
        
        Args:
            raw_text: Raw OCR text
            
        Returns:
            Filtered text with Reply to pattern extraction
        """
        import re
        
        if not raw_text or len(raw_text.strip()) < self.config.min_text_length:
            return ""
        
        # Remove excluded patterns first
        for pattern in self.config.excluded_patterns:
            if pattern.upper() in raw_text.upper():
                return ""
        
        raw = raw_text.strip()
        
        # CRITICAL: Exact filtering logic from quick_ocr_test.py
        # Try primary pattern with explicit ellipsis
        m = re.search(r"Reply to\s+([^\n\r]{2,60}?)\.\.\.", raw, re.I)
        if m:
            user = m.group(1).strip()
        else:
            # Fallback pattern without forcing ellipsis
            m = re.search(r"Reply to\s+([^\n\r]{2,60})", raw, re.I)
            user = m.group(1).strip() if m else None
        
        if user and user.endswith("..."):
            user = user[:-3].rstrip()
        
        # Final fallback: take first three words of OCR output
        if not user:
            tokens = raw.replace("\n", " ").split()
            user = " ".join(tokens[:3]) if tokens else None
        
        # Return the extracted user or 'NO USER' if nothing found
        return user if user else "NO USER"
    
    def validate_text_quality(self, text: str) -> Tuple[bool, str]:
        """
        Validate if extracted text meets quality standards.
        
        Args:
            text: Extracted text
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if not text:
            return False, "No text detected in the selected region."
        
        if len(text) < self.config.min_text_length:
            return False, f"Text too short (minimum {self.config.min_text_length} characters)."
        
        # Check for excluded patterns
        for pattern in self.config.excluded_patterns:
            if pattern.upper() in text.upper():
                return False, f"Excluded pattern detected: {pattern}"
        
        return True, "Text quality is acceptable."


def qpixmap_to_pil(qpixmap) -> Image.Image:
    """Convert QPixmap to PIL Image."""
    from PyQt6.QtCore import QBuffer, QIODevice
    
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    qpixmap.save(buffer, "PNG")
    
    pil_img = Image.open(io.BytesIO(buffer.data()))
    return pil_img


def pil_to_qpixmap(pil_img: Image.Image):
    """Convert PIL Image to QPixmap."""
    from PyQt6.QtGui import QPixmap
    
    buffer = io.BytesIO()
    pil_img.save(buffer, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap