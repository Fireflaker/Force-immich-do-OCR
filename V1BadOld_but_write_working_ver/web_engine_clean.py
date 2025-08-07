#!/usr/bin/env python3
"""
Web Engine module for Immich OCR Browser
Provides enhanced QWebEngineView with crop selection and automation features.

KEY INSIGHT: Proper device pixel ratio handling prevents quality loss.
- Use devicePixelRatioF() to get actual screen scaling
- Apply ratio to crop coordinates for accurate capture
- No artificial scaling needed if DPI handled correctly
"""

from PyQt6.QtWidgets import QMessageBox, QWidget, QRubberBand
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtCore import QRect, QPoint, Qt, QTimer, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QPainter, QPen, QColor
from typing import Optional, Tuple
from config import config


class SelectionOverlay(QWidget):
    """Transparent overlay widget for crop selection - COPIED FROM WORKING VERSION."""
    selectionFinished = pyqtSignal(QRect)
    
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowFlags(Qt.WindowType.Widget | Qt.WindowType.FramelessWindowHint)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.origin: Optional[QPoint] = None
        # Fill parent
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
        if self.origin and e.button() == Qt.MouseButton.LeftButton:
            rect = self.rubber.geometry()
            self.rubber.hide()
            self.selectionFinished.emit(rect)
            self.deleteLater()


class CropWebEngineView(QWebEngineView):
    """Enhanced QWebEngineView with rubber-band crop selection - FIXED WITH WORKING METHOD."""
    
    # Signal emitted when crop area is selected
    crop_selected = pyqtSignal(QRect)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.crop_rect: Optional[QRect] = None
        
        # Configure web engine settings
        self._setup_web_engine()
        
        # NEW: Restore last crop location if available
        self._restore_last_crop_location()
    
    def _setup_web_engine(self):
        """Configure web engine with automation-friendly settings."""
        from pathlib import Path
        
        # Create persistent profile for session retention (EXACT COPY from working version)
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
        
        # CRITICAL FIX: Create NEW page with profile (from working version)
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
            
            # Disable focus-dependent features
            try:
                settings.setAttribute(QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, False)
            except AttributeError:
                pass  # Attribute may not exist in all Qt versions
    
    def set_crop(self, rect: QRect):
        """Set the crop rectangle."""
        self.crop_rect = rect
    
    def get_crop_rect(self) -> Optional[QRect]:
        """Get the current crop rectangle."""
        return self.crop_rect
    
    def start_crop_mode(self):
        """Enable crop selection mode using overlay - WORKING METHOD."""
        overlay = SelectionOverlay(self)
        overlay.selectionFinished.connect(self._roi_selected)
        overlay.show()
    
    def _roi_selected(self, rect: QRect):
        """Handle crop selection completion - COPIED FROM WORKING VERSION."""
        self.crop_rect = rect
        
        # NEW: Save location for next session
        self._save_crop_location(rect)
        
        self.crop_selected.emit(rect)  # Emit signal for UI updates
    
    def clear_crop(self):
        """Clear the current crop selection."""
        self.crop_rect = None


class AutomationWebView(CropWebEngineView):
    """Web view with advanced automation capabilities."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.automation_timer = QTimer()
        self.automation_timer.timeout.connect(self._ensure_page_ready)
        
    def load_with_automation(self, url: str):
        """Load URL with automation preparations."""
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
    
    def _apply_initial_automation(self):
        """Apply initial automation scripts to the page."""
        from focus_solutions import focus_manager
        
        # Apply stealth mode immediately after page load
        if config.automation.stealth_mode:
            self.page().runJavaScript(focus_manager.get_stealth_script())
        
        # Apply focus override
        if config.automation.focus_override:
            self.page().runJavaScript(focus_manager.get_focus_override_script())
    
    def inject_text_with_automation(self, text: str) -> bool:
        """
        Inject text into Immich description field with comprehensive debugging.
        
        Focus: Identify the exact point where the application freezes during injection.
        
        Args:
            text: Text to inject into the description field
            
        Returns:
            bool: True if injection completed without freezing
        """
        try:
            print(f"🔧 DEBUG: Starting injection for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            
            # Escape text for JavaScript safely
            text_escaped = (text.replace('\\', '\\\\')
                              .replace("'", "\\'")
                              .replace('"', '\\"')
                              .replace('\n', '\\n')
                              .replace('\r', '\\r'))
            
            print(f"🔧 DEBUG: Text escaped successfully")
            
            # Simple, focused JavaScript with extensive debugging
            debug_injection_script = f"""
            (function() {{
                console.log('🔧 DEBUG: JavaScript execution started');
                console.log('🔧 DEBUG: Current URL:', window.location.href);
                console.log('🔧 DEBUG: Document ready state:', document.readyState);
                
                try {{
                    // Step 1: Find all possible form fields
                    console.log('🔧 DEBUG: Step 1 - Scanning for form fields...');
                    var allTextareas = document.querySelectorAll('textarea');
                    var allTextInputs = document.querySelectorAll('input[type="text"]');
                    
                    console.log('🔧 DEBUG: Found textareas:', allTextareas.length);
                    console.log('🔧 DEBUG: Found text inputs:', allTextInputs.length);
                    
                    // Step 2: Identify the description field
                    console.log('🔧 DEBUG: Step 2 - Looking for description field...');
                    var targetField = null;
                    
                    // Try description-specific selectors first
                    var descriptionSelectors = [
                        'textarea[placeholder*="description" i]',
                        'textarea[name*="description" i]',
                        'textarea[aria-label*="description" i]'
                    ];
                    
                    for (var selector of descriptionSelectors) {{
                        var field = document.querySelector(selector);
                        if (field) {{
                            targetField = field;
                            console.log('🔧 DEBUG: Found description field via selector:', selector);
                            break;
                        }}
                    }}
                    
                    // Fallback to any textarea
                    if (!targetField && allTextareas.length > 0) {{
                        targetField = allTextareas[0];
                        console.log('🔧 DEBUG: Using first textarea as fallback');
                    }}
                    
                    if (!targetField) {{
                        console.error('❌ DEBUG: No suitable field found');
                        return;
                    }}
                    
                    // Step 3: Log field details
                    console.log('🔧 DEBUG: Step 3 - Field analysis...');
                    console.log('🔧 DEBUG: Field tag:', targetField.tagName);
                    console.log('🔧 DEBUG: Field type:', targetField.type);
                    console.log('🔧 DEBUG: Field name:', targetField.name);
                    console.log('🔧 DEBUG: Field placeholder:', targetField.placeholder);
                    console.log('🔧 DEBUG: Field current value:', targetField.value);
                    console.log('🔧 DEBUG: Field disabled:', targetField.disabled);
                    console.log('🔧 DEBUG: Field readonly:', targetField.readOnly);
                    
                    // Step 4: Focus testing
                    console.log('🔧 DEBUG: Step 4 - Focus testing...');
                    console.log('🔧 DEBUG: Document has focus:', document.hasFocus());
                    console.log('🔧 DEBUG: Active element before:', document.activeElement);
                    
                    targetField.focus();
                    console.log('🔧 DEBUG: Focus called on field');
                    console.log('🔧 DEBUG: Active element after focus:', document.activeElement);
                    console.log('🔧 DEBUG: Field is focused:', document.activeElement === targetField);
                    
                    // Step 5: Value setting
                    console.log('🔧 DEBUG: Step 5 - Setting value...');
                    var originalValue = targetField.value;
                    targetField.value = '{text_escaped}';
                    console.log('🔧 DEBUG: Value set from "' + originalValue + '" to "' + targetField.value + '"');
                    
                    // Step 6: Event dispatch
                    console.log('🔧 DEBUG: Step 6 - Dispatching events...');
                    var events = ['input', 'change'];
                    events.forEach(function(eventType) {{
                        try {{
                            var event = new Event(eventType, {{ bubbles: true, cancelable: true }});
                            targetField.dispatchEvent(event);
                            console.log('🔧 DEBUG: Dispatched', eventType, 'event successfully');
                        }} catch(e) {{
                            console.error('❌ DEBUG: Error dispatching', eventType, ':', e);
                        }}
                    }});
                    
                    // Step 7: Verify final state
                    console.log('🔧 DEBUG: Step 7 - Final verification...');
                    console.log('🔧 DEBUG: Final field value:', targetField.value);
                    console.log('🔧 DEBUG: Field still focused:', document.activeElement === targetField);
                    
                    console.log('✅ DEBUG: JavaScript injection completed successfully');
                    
                }} catch (error) {{
                    console.error('❌ DEBUG: JavaScript error:', error);
                    console.error('❌ DEBUG: Error stack:', error.stack);
                }}
            }})();
            """
            
            print("🔧 DEBUG: About to execute JavaScript...")
            self.page().runJavaScript(debug_injection_script)
            print("🔧 DEBUG: JavaScript execution completed")
            
            return True
            
        except Exception as e:
            print(f"❌ DEBUG: Python exception: {e}")
            print(f"❌ DEBUG: Exception type: {type(e).__name__}")
            import traceback
            print(f"❌ DEBUG: Traceback: {traceback.format_exc()}")
            return False

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
        """
        Capture the selected crop area.
        
        CRITICAL: Must account for device pixel ratio for quality.
        Multiply crop coordinates by devicePixelRatioF() for accurate capture.
        
        PITFALL: devicePixelRatioF() varies by monitor (1.0, 1.25, 1.5, 2.0)
        Without scaling: crop coordinates are wrong on high-DPI displays
        With scaling: coordinates match actual pixel positions
        
        Returns:
            QPixmap of the cropped area or None if no crop is selected
        """
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
    """
    Factory function to create a properly configured automation web view.
    
    Args:
        parent: Parent widget
        
    Returns:
        Configured AutomationWebView instance
    """
    web_view = AutomationWebView(parent)
    
    # Apply any additional configuration
    web_view.setMinimumSize(800, 600)
    
    return web_view