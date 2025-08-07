#!/usr/bin/env python3
"""Immich OCR Helper (PySide6)

Uses Qt 6.9 → Chromium 110+ so Immich frontend works.

Functions:
1. Embedded browser with persistent cookies (auto-login once).
2. Click “Select ROI” → transparent overlay to draw crop rectangle.
3. Click “Run OCR” → shows preview + text then pastes into description.
4. ROI + cookies persist under ~/.immich_ocr_profile .
"""
from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageQt
import pytesseract, shutil, platform
from PySide6.QtCore import (QBuffer, QPoint, QRect, Qt, QSize, QUrl,
                            Signal, QEvent)
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWebEngineWidgets import QWebEngineView
try:
    from PySide6.QtWebEngineCore import QWebEngineProfile
except ImportError:
    from PySide6.QtWebEngineWidgets import QWebEngineProfile
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QRubberBand,
    QWidget,
    QToolBar,
    QDockWidget,
    QLabel,
    QTextEdit,
    QPushButton,
    QVBoxLayout,
)

HOME = Path.home() / ".immich_ocr_profile"

# ---------------------------------------------------------------------------
# Optional auto-login credentials (read from env or fallback below)
# ---------------------------------------------------------------------------
EMAIL = os.getenv("IMMICH_EMAIL", "lainflkr@gmail.com")
PASSWORD = os.getenv("IMMICH_PASSWORD", "leo83221266")
HOME.mkdir(exist_ok=True)

# Ensure Tesseract executable is discoverable on Windows
if platform.system() == "Windows" and shutil.which("tesseract") is None:
    default_path = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    if Path(default_path).exists():
        pytesseract.pytesseract.tesseract_cmd = default_path
ROI_FILE = HOME / "roi.json"

###############################################################################
# Utility helpers
###############################################################################

def qpixmap_to_pil(pix: QPixmap) -> Image.Image:
    buf = QBuffer()
    buf.open(QBuffer.ReadWrite)
    pix.save(buf, "PNG")
    return Image.open(BytesIO(buf.data()))

###############################################################################
# Transparent overlay for ROI selection
###############################################################################

class SelectionOverlay(QWidget):
    finished = Signal(QRect)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowFlags(Qt.WindowType.Widget | Qt.WindowType.FramelessWindowHint)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._origin: QPoint | None = None
        self.resize(parent.size())
        parent.installEventFilter(self)

    # keep overlay in sync with parent resize
    def eventFilter(self, obj, ev):
        if obj is self.parent() and ev.type() == QEvent.Type.Resize:
            self.resize(obj.size())
        return False

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._origin = e.pos()
            self._rubber.setGeometry(QRect(self._origin, QSize()))
            self._rubber.show()

    def mouseMoveEvent(self, e):
        if self._origin:
            self._rubber.setGeometry(QRect(self._origin, e.pos()).normalized())

    def mouseReleaseEvent(self, e):
        if self._origin and e.button() == Qt.MouseButton.LeftButton:
            rect = self._rubber.geometry()
            self._rubber.hide()
            self.finished.emit(rect)
            self.deleteLater()

###############################################################################
# Main window
###############################################################################

class MainWindow(QMainWindow):
    def __init__(self, url: str):
        super().__init__()
        self.setWindowTitle("Immich OCR Helper")
        self.resize(1500, 900)

        # persistent profile
        profile = QWebEngineProfile.defaultProfile()
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        profile.setPersistentStoragePath(str(HOME))

        # central web view
        self.web = QWebEngineView()
        self.setCentralWidget(self.web)
        self.web.loadFinished.connect(self._start_auto_login)
        self.web.load(QUrl(url))

        # ROI rectangle
        self.roi: QRect | None = self._load_roi()

        # toolbar
        tb = QToolBar()
        self.addToolBar(tb)
        act_roi = QAction("Select ROI", self)
        act_roi.triggered.connect(self._on_select_roi)
        tb.addAction(act_roi)
        act_run = QAction("Run OCR", self)
        act_run.triggered.connect(self._on_run_ocr)
        tb.addAction(act_run)

        # debug dock
        self.preview_label = QLabel("<ROI preview will appear here>")
        self.text_box = QTextEdit(); self.text_box.setReadOnly(True)
        btn_paste = QPushButton("Paste into description")
        btn_paste.clicked.connect(self._paste_text)
        dock_widget = QWidget(); lay = QVBoxLayout(dock_widget)
        lay.addWidget(self.preview_label); lay.addWidget(self.text_box); lay.addWidget(btn_paste)
        dock = QDockWidget("Debug", self); dock.setWidget(dock_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    # ---------------- auto-login ----------------
    # ------------- robust auto-login loop ---------------
    def _start_auto_login(self, ok: bool):
        if not ok:
            return
        self._login_attempts = 0
        from PySide6.QtCore import QTimer
        self._login_timer = QTimer(self)
        self._login_timer.setInterval(800)
        self._login_timer.timeout.connect(self._auto_login_step)
        self._login_timer.start()

    def _auto_login_step(self):
        self._login_attempts += 1
        js = f"""
        (function(){{
          const email=document.querySelector('input[type=email]');
          const pwd=document.querySelector('input[type=password]');
          if(email && pwd){{
            email.value='{EMAIL}';
            pwd.value='{PASSWORD}';
            const btn=document.querySelector('button[type=submit]')||document.querySelector('button');
            if(btn) btn.click();
            return 'filled';
          }}
          return 'nop';
        }})();"""
        def _cb(res):
            if res=='filled' or self._login_attempts>10:
                self._login_timer.stop()
        self.web.page().runJavaScript(js, _cb)

    # ---------------- selection -----------------
    def _on_select_roi(self):
        overlay = SelectionOverlay(self.web)
        overlay.finished.connect(self._roi_chosen)
        overlay.show()

    def _roi_chosen(self, rect: QRect):
        self.roi = rect
        self._save_roi(rect)
        QMessageBox.information(self, "ROI set", f"Saved region {rect.width()}×{rect.height()} px")

    # ---------------- OCR -----------------------
    def _on_run_ocr(self):
        if not self.roi or self.roi.isNull():
            QMessageBox.warning(self, "No ROI", "Select ROI first")
            return
        pix_full = self.web.grab()  # viewport pixmap
        dpr = pix_full.devicePixelRatioF() if hasattr(pix_full, "devicePixelRatioF") else pix_full.devicePixelRatio()
        if dpr != 1.0:
            r = self.roi
            rect_phys = QRect(int(r.x()*dpr), int(r.y()*dpr), int(r.width()*dpr), int(r.height()*dpr))
        else:
            rect_phys = self.roi
        pix_crop = pix_full.copy(rect_phys)
        pil_img = qpixmap_to_pil(pix_crop).convert("L")
        try:
            raw = pytesseract.image_to_string(pil_img, config="--psm 6").strip()
        except pytesseract.TesseractNotFoundError:
            QMessageBox.critical(self, "Tesseract not found", "Tesseract OCR engine is not installed or not in PATH.\nPlease install from https://github.com/tesseract-ocr/tesseract or adjust ocr_gui_pyside.py")
            return

        # Extract username from OCR output
        import re
        m = re.search(r"Reply to\s+([^\n\r]{2,60}?)\.\.\.", raw, re.IGNORECASE)
        if m:
            extracted = m.group(1).strip()
        else:
            m = re.search(r"Reply to\s+([^\n\r]{2,60})", raw, re.IGNORECASE)
            extracted = m.group(1).strip() if m else raw
        if extracted.endswith("..."):
            extracted = extracted[:-3].rstrip()

        # update debug widgets
        self.preview_label.setPixmap(QPixmap.fromImage(ImageQt.ImageQt(pil_img)).scaledToWidth(200))
        self.text_box.setPlainText(extracted)
        self._js_text = extracted

    def _paste_text(self):
        if not getattr(self, "_js_text", ""):
            return
        txt = self._js_text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
        js = f"(function(){{var ta=document.querySelector('textarea[placeholder=\"Add a description\"]');if(ta){{ta.value='OCR: {txt}';ta.dispatchEvent(new Event('input',{{bubbles:true}}));}}}})();"
        self.web.page().runJavaScript(js)

    # --------------- persistence ---------------
    def _save_roi(self, rect: QRect):
        with open(ROI_FILE, "w", encoding="utf-8") as f:
            json.dump({"x": rect.x(), "y": rect.y(), "w": rect.width(), "h": rect.height()}, f)

    def _load_roi(self) -> QRect | None:
        if not ROI_FILE.exists():
            return None
        try:
            data = json.loads(ROI_FILE.read_text())
            return QRect(data["x"], data["y"], data["w"], data["h"])
        except Exception:
            return None

###############################################################################
# Entry point
###############################################################################

def main():
    app = QApplication(sys.argv)
    url = "http://100.73.40.119:30041/"
    if len(sys.argv) > 1:
        url = sys.argv[1]
    win = MainWindow(url)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
