#!/usr/bin/env python3
# ⚠️  WARNING: THIS IS THE OLD MONOLITHIC VERSION ⚠️ 
# 
# DO NOT USE THIS FILE - IT HAS BEEN REPLACED BY MODULAR VERSION
# 
# PROBLEMS WITH THIS FILE:
# - Focus dependency (only works when window focused)
# - Single instance limitation
# - 700+ lines in one file
# - Artificial upscaling that hurts OCR quality
# 
# USE INSTEAD: main_app.py (modular version)
# Run: python main_app.py
# Or: ImmichOCR_Modular_v3.0.0/run_ImmichOCR_Modular.bat
"""Immich OCR Helper – Embedded browser + one-click OCR fill.

This minimal PyQt5 application embeds a full Chromium-based browser
(`QWebEngineView`) pointed at the Immich photos page.  The user can freely
interact with the web UI.  Whenever they want to extract text from a screen
region (for example the Snapchat *reply bar*) and paste that text into the
"Add a description" field, they:

1. Click the **Select Area** toolbar button and draw a rectangle over the
   browser with the left mouse button.  The rectangle is remembered as the
   Region of Interest (ROI).
2. Open any photo, make sure the description field is visible, and press the
   **Run OCR** button.  The application grabs the latest screenshot of the ROI,
   runs Tesseract OCR, and injects the recognised text into the description
   box via JavaScript.

The OCR routine re-uses the same Tesseract setup as the existing scripts – on
Windows it automatically falls back to the default installation path if
`tesseract.exe` isn’t on *PATH*.
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
from io import BytesIO
from pathlib import Path

import argparse
import re
import subprocess
import uuid


from PIL import Image, ImageEnhance
import pytesseract

try:
    # Try PySide6 first since it's in requirements.txt
    from PySide6.QtCore import (
        QBuffer,
        QPoint,
        QRect,
        Qt,
        QSize,
        QUrl,
        QEvent,
        QTimer,
        Signal as pyqtSignal,
    )
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtGui import QAction, QKeyEvent, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QMainWindow,
        QMessageBox,
        QRubberBand,
        QToolBar,
        QWidget,
        QLabel,
        QSpinBox,
        QVBoxLayout,
    )

    PYQT = 0  # Using a different value to distinguish from PyQt5/6
except ImportError:
    try:
        from PyQt6.QtCore import (
            QBuffer,
            QPoint,
            QRect,
            Qt,
            QSize,
            QUrl,
            QEvent,
            QTimer,
            pyqtSignal,
        )
        from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtGui import QAction, QKeyEvent, QPixmap
        from PyQt6.QtWidgets import (
            QApplication,
            QMainWindow,
            QMessageBox,
            QRubberBand,
            QToolBar,
            QWidget,
            QLabel,
            QSpinBox,
            QVBoxLayout,
        )

        PYQT = 6
    except ImportError:
        from PyQt5.QtCore import (
            QBuffer,
            QPoint,
            QRect,
            Qt,
            QSize,
            QUrl,
            QEvent,
            QTimer,
            pyqtSignal,
        )
        from PyQt5.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        from PyQt5.QtGui import QKeyEvent, QPixmap
        from PyQt5.QtWidgets import (
            QAction,
            QApplication,
            QMainWindow,
            QMessageBox,
            QRubberBand,
            QToolBar,
            QWidget,
            QLabel,
            QSpinBox,
            QVBoxLayout,
        )

        PYQT = 5

QT_LEFT = Qt.MouseButton.LeftButton if PYQT in (0, 6) else Qt.LeftButton
QT_CTRL = Qt.KeyboardModifier.ControlModifier if PYQT in (0, 6) else Qt.ControlModifier
RUBBER_RECT = QRubberBand.Shape.Rectangle if PYQT in (0, 6) else QRubberBand.Rectangle
SMOOTH_TRANSFORM = (
    Qt.TransformationMode.SmoothTransformation if PYQT in (0, 6) else Qt.SmoothTransformation
)







###############################################################################
# Helper – ensure Tesseract executable is found on Windows automatically
###############################################################################
if platform.system() == "Windows" and shutil.which("tesseract") is None:
    default_tess = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    if Path(default_tess).exists():
        pytesseract.pytesseract.tesseract_cmd = default_tess

###############################################################################
# Utility:  convert Qt pixmap → PIL.Image for Tesseract
###############################################################################

def qpixmap_to_pil(pixmap):
    """Converts a QPixmap to a PIL Image."""
    buffer = QBuffer()
    buffer.open(QBuffer.ReadWrite)
    pixmap.save(buffer, "PNG")
    pil_img = Image.open(BytesIO(buffer.data()))
    return pil_img


def pil_to_qpixmap(pil_img):
    """Converts a PIL Image to a QPixmap."""
    buffer = BytesIO()
    pil_img.save(buffer, "PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap


def _preprocess_for_ocr(pil_img: Image.Image) -> Image.Image:
    """Optimizes image for OCR without artificial upscaling."""
    # Convert to grayscale first - this often improves OCR accuracy
    gray_img = pil_img.convert("L")
    
    # Apply very mild Gaussian blur to reduce noise without losing text detail
    # Radius of 0.3 is very subtle and helps with aliasing/noise
    from PIL import ImageFilter
    denoised = gray_img.filter(ImageFilter.GaussianBlur(radius=0.3))
    
    # Conservative contrast enhancement - avoids creating artifacts
    from PIL import ImageEnhance
    enhancer = ImageEnhance.Contrast(denoised)
    contrast_img = enhancer.enhance(1.2)  # Much more conservative than 2.2
    
    # Optional: Apply very mild sharpening only to help with text edges
    # This helps with text edges without creating artifacts
    sharpener = ImageFilter.UnsharpMask(radius=0.5, percent=100, threshold=2)
    final_img = contrast_img.filter(sharpener)

    return final_img


###############################################################################
# Custom WebEngine view with rubber-band ROI selection support
###############################################################################

# ---------------------------------------------------------------------------
# Transparent overlay widget for region selection
# ---------------------------------------------------------------------------


class SelectionOverlay(QWidget):
    selectionFinished = pyqtSignal(QRect)
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setWindowFlags(Qt.Widget | Qt.FramelessWindowHint)
        self.setCursor(Qt.CrossCursor)
        self.rubber = QRubberBand(RUBBER_RECT, self)
        self.origin: QPoint | None = None
        # fill parent
        self.resize(parent.size())
        parent.installEventFilter(self)
    def eventFilter(self, obj, ev):

        if obj is self.parent() and ev.type() == QEvent.Resize:
            self.resize(obj.size())
        return False
    def mousePressEvent(self, e):
        if e.button() == QT_LEFT:
            self.origin = e.pos()
            self.rubber.setGeometry(QRect(self.origin, QSize()))
            self.rubber.show()
    def mouseMoveEvent(self, e):
        if self.origin:
            self.rubber.setGeometry(QRect(self.origin, e.pos()).normalized())
    def mouseReleaseEvent(self, e):
        if self.origin and e.button() == QT_LEFT:
            rect = self.rubber.geometry()
            self.rubber.hide()
            self.selectionFinished.emit(rect)
            self.deleteLater()

class ROIWebView(QWebEngineView):
    """QWebEngineView that stores the last ROI rectangle (set externally)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.crop_rect: QRect | None = None

    def set_crop(self, rect: QRect):
        self.crop_rect = rect

###############################################################################
# Main application window
###############################################################################

class OcrPreviewWidget(QWidget):
    """A non-modal widget to display OCR results."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OCR Result Preview")
        # Use Tool flag to make it a floating window that doesn't block the parent
        self.setWindowFlags(self.windowFlags() | Qt.Tool)

        self.layout = QVBoxLayout(self)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)

        self.layout.addWidget(self.image_label)
        self.layout.addWidget(self.text_label)

    def update_content(self, pixmap, text):
        # Gracefully handle cases where the pixmap might be null
        if pixmap and not pixmap.isNull():
            self.image_label.setPixmap(pixmap.scaledToWidth(500, SMOOTH_TRANSFORM))
        else:
            self.image_label.clear()
        self.text_label.setText(f"<b>OCR Text:</b><br/>{text}")

    def closeEvent(self, event):
        # Override close event to just hide the window, allowing it to be reused
        self.hide()
        event.ignore()

class MainWindow(QMainWindow):
    def __init__(self, url: str, profile_name: str, geometry_str: str | None, crop_str: str | None, delay: int | None):
        super().__init__()
        self.setWindowTitle(f"Immich OCR - {profile_name}")
        self.resize(1400, 900)

        # Apply geometry if provided
        if geometry_str:
            try:
                x, y, w, h = map(int, geometry_str.split(","))
                self.setGeometry(x, y, w, h)
            except (ValueError, IndexError):
                print(f"Warning: Invalid geometry string: {geometry_str}")

        # -------------------------- Main Toolbar ---------------------------
        self.tb = QToolBar("Main")
        self.tb.setIconSize(QSize(16, 16))
        self.tb.setEnabled(False)  # Disable until page is loaded

        launch_act = QAction("New Instance", self)
        launch_act.setStatusTip("Launch another instance with the same settings")
        launch_act.triggered.connect(self._launch_new_instance)
        self.tb.addAction(launch_act)

        self.tb.addSeparator()

        select_act = QAction("Select Area", self)
        select_act.setStatusTip("Click then drag on the page to mark the region used for OCR")
        select_act.triggered.connect(self._start_roi_selection)
        self.tb.addAction(select_act)

        run_act = QAction("Run OCR", self)
        run_act.setStatusTip("Run OCR on the selected area and paste into Immich description")
        run_act.triggered.connect(self._run_ocr)
        self.tb.addAction(run_act)

        # -------------------- Automation Toolbar ----------------------
        self.auto_tb = QToolBar("Automation")
        self.auto_tb.setIconSize(QSize(16, 16))
        self.auto_tb.setEnabled(False)  # Disable until page is loaded

        self.start_action = QAction("Start Loop", self)
        self.start_action.triggered.connect(self._start_loop)
        self.auto_tb.addAction(self.start_action)

        self.stop_action = QAction("Stop Loop", self)
        self.stop_action.triggered.connect(self._stop_loop)
        self.stop_action.setEnabled(False)
        self.auto_tb.addAction(self.stop_action)

        self.auto_tb.addSeparator()

        self.prev_action = QAction("Previous", self)
        self.prev_action.triggered.connect(self._navigate_prev)
        self.auto_tb.addAction(self.prev_action)

        self.next_action = QAction("Next", self)
        self.next_action.triggered.connect(self._navigate_next)
        self.auto_tb.addAction(self.next_action)

        self.auto_tb.addSeparator()
        self.auto_tb.addWidget(QLabel(" Delay (ms): "))
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(100, 10000)
        self.delay_spinbox.setValue(delay if delay else 800)
        self.delay_spinbox.setSingleStep(50)
        self.auto_tb.addWidget(self.delay_spinbox)

        self.addToolBar(self.auto_tb)
        self.addToolBarBreak()
        self.addToolBar(self.tb)

        # ----------------------- Automation Logic -------------------------
        self.loop_active = False
        self.loop_state = "OCR"  # Start by assuming we should OCR the current image

        # -------------------- OCR Preview Dialog ----------------------
        self.preview_dialog = OcrPreviewWidget()

        # ---------------------- Web Profile & Cookies ---------------------
        profile_dir_name = f".immich_ocr_profile_{profile_name}"
        profile_path = str(Path.home() / profile_dir_name)

        # Use the profile name for both the object and the on-disk storage
        profile = QWebEngineProfile(profile_name, self)
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        profile.setPersistentStoragePath(profile_path)

        # ----------------------- Embedded web -------------------------
        self.web = ROIWebView(self)
        if crop_str:
            try:
                l, t, w, h = map(int, crop_str.split(","))
                self.web.set_crop(QRect(l, t, w, h))
            except (ValueError, IndexError):
                print(f"Warning: Invalid crop string: {crop_str}")

        page = QWebEnginePage(profile, self.web)
        self.web.setPage(page)
        self.setCentralWidget(self.web)
        self.web.loadFinished.connect(self._on_load_finished)
        self.web.load(QUrl(url))

    # ------------------------------------------------------------------
    # Slots / helpers
    # ------------------------------------------------------------------

    def _show_selection_help(self):  # noqa: D401
        QMessageBox.information(
            self,
            "Select ROI",
            "Click 'Select Area' then drag with the mouse to draw the rectangle that contains text you want to OCR.",
        )

    def _start_roi_selection(self):  # noqa: D401
        # Create transparent overlay for selection
        overlay = SelectionOverlay(self.web)
        overlay.selectionFinished.connect(self._roi_selected)
        overlay.show()

    def _roi_selected(self, rect: QRect):  # noqa: D401
        self.web.set_crop(rect)
        # simple feedback
        QMessageBox.information(self, "ROI", f"Region set: {rect.width()}×{rect.height()} px")

    def _run_ocr(self):  # noqa: D401
        if not self.web.crop_rect or self.web.crop_rect.isNull():
            QMessageBox.warning(self, "No area selected", "Please select a region first.")
            return

        # Get the display's actual pixel ratio for proper scaling
        pixel_ratio = self.web.devicePixelRatioF()
        pixmap = self.web.grab()

        # Scale crop rectangle to match physical pixels
        crop_rect = QRect(
            int(self.web.crop_rect.left() * pixel_ratio),
            int(self.web.crop_rect.top() * pixel_ratio),
            int(self.web.crop_rect.width() * pixel_ratio),
            int(self.web.crop_rect.height() * pixel_ratio),
        )
        crop = pixmap.copy(crop_rect)
        pil_img = qpixmap_to_pil(crop)

        # Preprocess the image for better OCR results
        processed_pil_img = _preprocess_for_ocr(pil_img)

        # Run OCR on the processed image
        raw_text = pytesseract.image_to_string(processed_pil_img, config="--psm 6").strip()
        text = self._filter_ocr_text(raw_text)

        if not text or text == "NO USER":
            self.preview_dialog.update_content(QPixmap(), "No text detected in the selected region.")
            self.preview_dialog.show()
            return

        # Sanitize for JS single-quoted string and prepare the script
        text_js = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
        # Apply comprehensive focus solutions first
        stealth_js = """
(function() {
    // SOLUTION 1: Stealth Mode - Hide automation detection
    if (window.chrome && window.chrome.runtime && window.chrome.runtime.onConnect) {
        delete window.chrome.runtime.onConnect;
    }
    delete window.navigator.webdriver;
    Object.defineProperty(navigator, 'plugins', {
        get: function() { return [1, 2, 3, 4, 5]; }
    });
    
    // SOLUTION 2: Focus Override - Force always-focused state
    Object.defineProperty(document, 'hidden', {
        get: function() { return false; }, configurable: true
    });
    Object.defineProperty(document, 'visibilityState', {
        get: function() { return 'visible'; }, configurable: true
    });
    Document.prototype.hasFocus = function() { return true; };
    window.onblur = null;
    window.onfocus = function() { return true; };
    
    console.log('Stealth and focus override activated');
})();
"""
        
        # Apply stealth mode first
        self.web.page().runJavaScript(stealth_js)
        
        # Main injection script with comprehensive approach
        js = f"""(function(){{
  var ta = document.querySelector('textarea[placeholder=\"Add a description\"]');
  if(!ta) return;
  
  // SOLUTION 3: Multi-method focus forcing
  function forceRealFocus(element) {{
    // Multiple focus attempts
    element.focus();
    element.click();
    element.select();
    
    // Force active element override
    Object.defineProperty(document, 'activeElement', {{
        get: function() {{ return element; }},
        configurable: true
    }});
    
    // Continuous refocus (disabled after input)
    var refocusInterval = setInterval(function() {{
        if (document.activeElement !== element) {{
            element.focus();
        }}
    }}, 50);
    
    // Stop refocusing after 2 seconds
    setTimeout(function() {{ clearInterval(refocusInterval); }}, 2000);
  }}
  
  // SOLUTION 4: Advanced input simulation
  function simulateRealInput(element, text) {{
    forceRealFocus(element);
    
    // Clear existing content with multiple methods
    element.value = '';
    element.textContent = '';
    element.innerHTML = '';
    
    // Set value using native property descriptor
    var nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    nativeSetter.call(element, text);
    
    // Trigger comprehensive event sequence
    var events = ['focus', 'click', 'input', 'change', 'keydown', 'keyup', 'blur', 'focus'];
    events.forEach(function(eventType) {{
        var event = new Event(eventType, {{ bubbles: true, cancelable: true, composed: true }});
        element.dispatchEvent(event);
    }});
    
    // SOLUTION 5: Multiple save attempts with different methods
    setTimeout(function() {{
        // Method 1: Ctrl+Enter on element
        var ctrlEnter = new KeyboardEvent('keydown', {{
            key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
            ctrlKey: true, bubbles: true, cancelable: true, composed: true
        }});
        element.dispatchEvent(ctrlEnter);
        
        // Method 2: Ctrl+Enter on document
        document.dispatchEvent(ctrlEnter);
        
        // Method 3: Ctrl+Enter on window  
        window.dispatchEvent(ctrlEnter);
        
        // Method 4: Try form submission if textarea is in a form
        var form = element.closest('form');
        if (form) {{
            form.dispatchEvent(new Event('submit', {{ bubbles: true, cancelable: true }}));
        }}
        
        // Method 5: Try clicking save buttons
        var saveButtons = document.querySelectorAll('button[type="submit"], button:contains("Save"), [aria-label*="save" i]');
        saveButtons.forEach(function(btn) {{ btn.click(); }});
        
    }}, 100);
  }}
  
  // Execute the comprehensive input simulation
  simulateRealInput(ta, '{text_js}');
  
}})();"""

        # Convert the processed PIL image back to a QPixmap for the preview
        processed_pixmap = pil_to_qpixmap(processed_pil_img)

        # Update and show the persistent preview dialog
        self.preview_dialog.update_content(processed_pixmap, text)
        self.preview_dialog.show()

        # Inject into page
        self.web.page().runJavaScript(js)

    def _filter_ocr_text(self, raw_text: str) -> str:
        """Cleans the raw OCR output to extract a username."""
        # Try primary pattern with explicit ellipsis
        m = re.search(r"Reply to\s+([^\n\r]{2,60}?)\.\.\.", raw_text, re.I)
        if m:
            user = m.group(1).strip()
        else:
            # Fallback pattern without forcing ellipsis
            m = re.search(r"Reply to\s+([^\n\r]{2,60})", raw_text, re.I)
            user = m.group(1).strip() if m else None

        if user and user.endswith("..."):
            user = user[:-3].rstrip()

        # Final fallback: take first three words of OCR output
        if not user:
            tokens = raw_text.replace("\n", " ").split()
            user = " ".join(tokens[:3]) if tokens else "NO USER"

        return user or "NO USER"

    def _navigate_next(self):
        """Executes JS to click the 'next asset' button in the UI."""
        js = "document.querySelector('button[aria-label=\"View next asset\"]').click();"
        self.web.page().runJavaScript(js)

    def _navigate_prev(self):
        """Executes JS to click the 'previous asset' button in the UI."""
        js = "document.querySelector('button[aria-label=\"View previous asset\"]').click();"
        self.web.page().runJavaScript(js)

    def _start_loop(self):
        """Starts the automation loop."""
        if self.loop_active:
            return
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.prev_action.setEnabled(False)
        self.next_action.setEnabled(False)
        self.delay_spinbox.setEnabled(False)
        self.loop_active = True
        self.loop_state = "OCR"
        self._automation_step()

    def _stop_loop(self):
        """Stops the automation loop."""
        self.loop_active = False
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.prev_action.setEnabled(True)
        self.next_action.setEnabled(True)
        self.delay_spinbox.setEnabled(True)

    def _automation_step(self):
        """A simple state machine for the automation loop."""
        if not self.loop_active:
            return

        delay = self.delay_spinbox.value()

        if self.loop_state == "OCR":
            self._run_ocr()
            self.loop_state = "NAVIGATE"
            QTimer.singleShot(delay, self._automation_step)
        elif self.loop_state == "NAVIGATE":
            self._navigate_next()
            self.loop_state = "OCR"
            QTimer.singleShot(delay, self._automation_step)

    def _on_load_finished(self, ok):
        """Callback for when the page has finished loading."""
        if ok:
            self.tb.setEnabled(True)
            self.auto_tb.setEnabled(True)
        else:
            QMessageBox.critical(self, "Load Error", "Failed to load Immich. Please check the URL and your connection.")

    def _launch_new_instance(self):
        """Launches a new instance of the app with the same settings."""
        args = [sys.executable, __file__]

        # Pass current URL
        args.append(self.web.url().toString())

        # Generate a new unique profile name
        args.extend(["--profile", str(uuid.uuid4().hex[:8])])

        # Pass current geometry
        geom = self.geometry()
        args.extend(["--geometry", f"{geom.x()},{geom.y()},{geom.width()},{geom.height()}"])

        # Pass current crop rectangle
        if self.web.crop_rect and not self.web.crop_rect.isNull():
            rect = self.web.crop_rect
            args.extend(["--crop", f"{rect.x()},{rect.y()},{rect.width()},{rect.height()}"])

        # Pass current delay
        args.extend(["--delay", str(self.delay_spinbox.value())])

        # Launch a new detached process
        subprocess.Popen(args)


###############################################################################
# Entry point
###############################################################################

def main():  # noqa: D401
    parser = argparse.ArgumentParser(description="Immich OCR Helper")
    parser.add_argument(
        "url",
        nargs="?",
        default="http://100.73.40.119:30041/",
        help="The Immich URL to load.",
    )
    parser.add_argument(
        "--profile",
        default="default",
        help="A unique profile name for this instance.",
    )
    parser.add_argument("--geometry", help="Initial window geometry (x,y,w,h).")
    parser.add_argument("--crop", help="Initial crop rectangle (l,t,w,h).")
    parser.add_argument("--delay", type=int, help="Initial delay in ms.")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    win = MainWindow(
        url=args.url,
        profile_name=args.profile,
        geometry_str=args.geometry,
        crop_str=args.crop,
        delay=args.delay,
    )
    win.show()

    if PYQT in (0, 6):
        sys.exit(app.exec())
    else:
        sys.exit(app.exec_())


if __name__ == "__main__":
    main()
