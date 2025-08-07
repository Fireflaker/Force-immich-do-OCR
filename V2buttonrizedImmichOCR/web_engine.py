#!/usr/bin/env python3
"""
CLEAN Web Engine module for Immich OCR Browser - FIXED VERSION
Provides enhanced QWebEngineView with proper focus automation.
"""

from PyQt6.QtWidgets import QMessageBox, QWidget, QRubberBand
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtCore import QRect, QPoint, Qt, QTimer, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QPainter, QPen, QColor
from typing import Optional, Tuple
from config import config


class SelectionOverlay(QWidget):
    """Transparent overlay widget for crop selection."""
    selectionFinished = pyqtSignal(QRect)
    
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowFlags(Qt.WindowType.Widget | Qt.WindowType.FramelessWindowHint)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.origin: Optional[QPoint] = None
        self.resize(parent.size())
        parent.installEventFilter(self)
    
    def eventFilter(self, obj, ev):
        if obj is self.parent() and ev.type() == QEvent.Type.Resize:
            self.resize(obj.size())
        return False
    
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.origin = e.position().toPoint()
            self.rubber.setGeometry(QRect(self.origin, QSize()))
            self.rubber.show()
    
    def mouseMoveEvent(self, e):
        if self.origin:
            self.rubber.setGeometry(QRect(self.origin, e.position().toPoint()).normalized())
    
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.origin:
            rect = QRect(self.origin, e.position().toPoint()).normalized()
            self.rubber.hide()
            self.hide()
            self.selectionFinished.emit(rect)
            self.origin = None


class AutomationWebView(QWebEngineView):
    """Enhanced QWebEngineView with comprehensive automation capabilities."""
    
    cropSelectionFinished = pyqtSignal(QRect)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._configure_web_engine()
        self.crop_rect: Optional[QRect] = None
        self.automation_timer = QTimer()
        self.automation_timer.timeout.connect(self._ensure_page_ready)
        self._restore_last_crop_location()
    
    def load(self, url):
        """Load URL with automation preparations."""
        super().load(url)
        QTimer.singleShot(1000, self._setup_page_automation)
    
    def load_with_automation(self, url):
        """Load URL with automation preparations and monitoring."""
        # Start monitoring page readiness
        self.automation_timer.start(1000)  # Check every second
        self.load(url)
    
    def _ensure_page_ready(self):
        """Ensure page is ready for automation."""
        # Check if page is loaded
        if self.page().isLoading():
            return
        
        # Stop the timer once page is loaded
        self.automation_timer.stop()
        
        # Apply initial automation setup
        self._apply_initial_automation()
    
    def _setup_page_automation(self):
        """Ensure page is ready for automation."""
        print("🔧 Setting up page automation...")
        
    def _apply_initial_automation(self):
        """Apply initial automation setup after page loads."""
        from focus_solutions import focus_manager
        
        # Apply stealth mode immediately after page load
        if config.automation.stealth_mode:
            self.page().runJavaScript(focus_manager.get_stealth_script())
        
        # Apply focus override - TEMPORARILY DISABLED FOR TESTING
        # if config.automation.focus_override:
        #     self.page().runJavaScript(focus_manager.get_focus_override_script())
        
    def _configure_web_engine(self):
        """Configure web engine with automation-friendly settings."""
        from pathlib import Path
        
        # Create persistent profile for session retention (EXACT COPY from working V1)
        profile_name = "immich_ocr_persistent"  
        profile_dir_name = f".immich_ocr_profile_{profile_name}"
        profile_path = str(Path.home() / profile_dir_name)
        
        # Ensure profile directory exists
        Path(profile_path).mkdir(parents=True, exist_ok=True)
        
        profile = QWebEngineProfile(profile_name, self)
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        profile.setPersistentStoragePath(profile_path)
        
        # Set user agent
        profile.setHttpUserAgent(config.web_engine.user_agent)
        
        # CRITICAL FIX: Create NEW page with profile (from working V1)
        # PITFALL: Using setProfile() on existing page doesn't work reliably
        # SOLUTION: Create new page with profile, then assign to view
        page = QWebEnginePage(profile, self)
        self.setPage(page)
        
        # CRITICAL: Apply Chrome automation flags
        try:
            import os
            chrome_flags = ' '.join(config.get_chrome_flags())
            os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = chrome_flags
        except Exception as e:
            print(f"Warning: Could not set Chrome flags: {e}")
        
        # Configure settings
        settings = self.settings()
        if hasattr(settings, 'setAttribute'):
            # Enable various features for better automation
            from PyQt6.QtWebEngineCore import QWebEngineSettings
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, False)
            
            # Disable focus-dependent features that can interfere
            try:
                settings.setAttribute(QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, False)
            except AttributeError:
                pass  # Attribute may not exist in all Qt versions
    
    def inject_text_with_automation(self, text: str, finished_cb=None) -> bool:
        """
        Inject text using Immich's EXACT save mechanism (focusout event).
        
        Based on source code analysis of detail-panel-description.svelte:
        - Save is triggered by onfocusout={updateContent} on AutogrowTextarea
        - This calls handleFocusOut -> updateAsset API -> success notification
        - NOT form submission!
        
        Args:
            text: Text to inject into the description field
            finished_cb: Optional callback for async result handling
            
        Returns:
            bool: True if script was dispatched successfully, False on exception
        """
        try:
            print(f"📝 Starting Immich-specific automation for: '{text[:50]}...'")
            
            # Immich-specific script based on source code analysis
            simple_script = f"""
(function() {{
    console.log('🎯 Starting Immich-specific automation (focusout-based save)...');
    
    // Find the textarea using the exact selector we know works
    var textarea = document.querySelector('textarea[data-testid="autogrow-textarea"]');
    
                if (!textarea) {{
        console.log('❌ ERROR: Textarea not found with selector: textarea[data-testid="autogrow-textarea"]');
                    return false;
                }}

    console.log('✅ Found textarea, applying focus and text...');
    
    // Clear any existing text
    textarea.value = '';
    
    // Step 1: Focus the textarea (triggers blue underline)
    textarea.focus();
    console.log('✅ Focused textarea');
    
    // Step 2: Set the text value (simulates typing)
    textarea.value = `{text}`;
    console.log('✅ Set textarea value to: ' + `{text}`.substring(0, 50) + '...');
    
    // Step 3: Trigger input event (notifies Svelte of value change)
    textarea.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
    console.log('✅ Triggered input event');
    
    // Step 4: CRITICAL - Trigger focusout event (this is what saves in Immich!)
    // From source: onfocusout={{updateContent}} -> onContentUpdate(newContent) -> handleFocusOut -> updateAsset API
    textarea.blur(); // Remove focus (triggers focusout)
    textarea.dispatchEvent(new Event('focusout', {{ bubbles: true, cancelable: true }}));
    console.log('🎯 CRITICAL: Triggered focusout event - this should save to Immich!');
    
    // Optional: Verify the save by checking for notification
    setTimeout(function() {{
        var notifications = document.querySelectorAll('[data-testid="notification"]');
        if (notifications.length > 0) {{
            console.log('✅ Found notification elements - save likely successful');
        }}
    }}, 500);
    
    console.log('🎉 Simple automation completed');
    return true;
            }})();
            """
            
            print("🔥 Executing Immich-specific automation script...")
            
            # Execute the focusout-based script
            if finished_cb:
                def _js_callback(result):
                    print(f"📊 Simple automation result: {result}")
                    finished_cb(result)
                
                self.page().runJavaScript(simple_script, _js_callback)
            else:
                self.page().runJavaScript(simple_script)
            
            print("✅ Immich-specific automation script executed")
            return True
            
        except Exception as e:
            print(f"❌ Exception during simple automation: {e}")
            import traceback
            traceback.print_exc()
            return False

    def set_crop_rect(self, rect: QRect):
        """Set the crop rectangle."""
        self.crop_rect = rect
    
    def get_crop_rect(self) -> Optional[QRect]:
        """Get the current crop rectangle."""
        return self.crop_rect
    
    def start_crop_mode(self):
        """Enable crop selection mode using overlay."""
        if not hasattr(self, 'overlay'):
            self.overlay = SelectionOverlay(self)
            self.overlay.selectionFinished.connect(self._on_crop_selected)
        self.overlay.show()
    
    def _on_crop_selected(self, rect: QRect):
        """Handle crop selection completion."""
        print(f"🎯 Crop selected: {rect.x()}, {rect.y()}, {rect.width()}x{rect.height()}")
        self.crop_rect = rect
        self._save_crop_location(rect)
        self.cropSelectionFinished.emit(rect)
    
    def clear_crop(self):
        """Clear the current crop selection."""
        self.crop_rect = None
        self.update()

    def _save_crop_location(self, rect: QRect):
        """Save the current crop location for next session."""
        try:
            from config import config
            config.ocr_location.save_location(
                rect.x(), rect.y(), rect.width(), rect.height()
            )
            print(f"💾 Saved crop location: {rect.x()}, {rect.y()}, {rect.width()}x{rect.height()}")
        except Exception as e:
            print(f"⚠️ Failed to save crop location: {e}")
    
    def _restore_last_crop_location(self):
        """Restore the last saved crop location if available."""
        try:
            from config import config
            if config.ocr_location.has_saved_location():
                self.crop_rect = QRect(
                    config.ocr_location.last_crop_x,
                    config.ocr_location.last_crop_y,
                    config.ocr_location.last_crop_width,
                    config.ocr_location.last_crop_height
                )
                print(f"🔄 Restored crop location: {self.crop_rect.x()}, {self.crop_rect.y()}, {self.crop_rect.width()}x{self.crop_rect.height()}")
            else:
                print("ℹ️ No saved crop location found")
        except Exception as e:
            print(f"⚠️ Failed to restore crop location: {e}")
    
    def capture_crop_area(self) -> Optional['QPixmap']:
        """Capture the selected crop area with proper DPI handling."""
        if not self.crop_rect or self.crop_rect.isNull():
            return None
        
        # Get device pixel ratio for proper scaling
        pixel_ratio = self.devicePixelRatioF()
        pixmap = self.grab()
        
        # Scale crop rectangle to match physical pixels
        crop_rect = QRect(
            int(self.crop_rect.left() * pixel_ratio),
            int(self.crop_rect.top() * pixel_ratio),
            int(self.crop_rect.width() * pixel_ratio),
            int(self.crop_rect.height() * pixel_ratio),
        )
        
        # Return cropped pixmap
        return pixmap.copy(crop_rect)


def create_automation_web_view(parent=None) -> AutomationWebView:
    """Factory function to create a properly configured automation web view."""
    web_view = AutomationWebView(parent)
    web_view.setMinimumSize(800, 600)
    return web_view