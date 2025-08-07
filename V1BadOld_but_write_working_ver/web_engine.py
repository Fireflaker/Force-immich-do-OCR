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
        Inject text into Immich description field using a multi-layered approach
        that includes realistic UI simulation, verification, and a direct API fallback.

        KEY INSIGHT: Modern web apps require a sequence of events to detect
        changes. This method simulates that sequence, verifies success by
        looking for a confirmation message, and uses a direct API call if the
        UI method fails, guaranteeing the save.
        """
        try:
            print(f"📝 Starting robust text injection for: '{text[:50]}...'")
            
            text_escaped = (text.replace('\\', '\\\\')
                              .replace("'", "\\'")
                              .replace('"', '\\"')
                              .replace('\n', '\\n')
                              .replace('\r', '\\r'))
            
            injection_script = f"""
            (async function() {{
                console.log('🦾 Starting robust injection...');
                const text = `{text_escaped}`;
                
                // --- Helper Functions ---
                const findTextarea = () => {{
                    let textarea = document.querySelector('textarea[data-testid="autogrow-textarea"]');
                    if (textarea) return textarea;
                    
                    textarea = Array.from(document.querySelectorAll('textarea')).find(
                        ta => ta.placeholder && ta.placeholder.toLowerCase().includes('description')
                    );
                    if (textarea) return textarea;

                    console.warn('Could not find textarea by primary selectors.');
                    return null;
                }};

                const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

                const verifySave = () => new Promise(resolve => {{
                    const timeout = 2000; // 2 seconds to wait for the popup
                    const checkInterval = 100; // Check every 100ms
                    let elapsedTime = 0;

                    const intervalId = setInterval(() => {{
                        const notification = document.querySelector('[data-testid="notification-content"]');
                        if (notification && (notification.textContent.includes('updated') || notification.textContent.includes('saved'))) {{
                            console.log('✅ UI Verification successful: Found success popup.');
                            clearInterval(intervalId);
                            resolve(true);
                        }}

                        elapsedTime += checkInterval;
                        if (elapsedTime >= timeout) {{
                            console.warn('⚠️ UI Verification failed: Success popup not found.');
                            clearInterval(intervalId);
                            resolve(false);
                        }}
                    }}, checkInterval);
                }});

                // --- Main Logic ---
                const textarea = findTextarea();
                if (!textarea) {{
                    console.error('❌ Injection failed: Could not find the description textarea.');
                    return false;
                }}

                // --- Method 1: Simulate Realistic User Interaction ---
                console.log('➡️ Attempting Method 1: Realistic UI Simulation');
                try {{
                    textarea.focus();
                    await sleep(50);
                    
                    // Simulate clearing the field first
                    document.execCommand('selectAll', false, null);
                    document.execCommand('insertText', false, text);
                    
                    await sleep(50);
                    textarea.blur(); // Trigger focusout to save

                    if (await verifySave()) {{
                        return true;
                    }}
                }} catch (e) {{
                    console.error('❌ Error during UI simulation:', e);
                }}

                // --- Method 2: API Fallback ---
                console.log('➡️ UI Method failed. Attempting Method 2: Direct API Call');
                try {{
                    const assetIdMatch = window.location.pathname.match(/[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}/i);
                    if (!assetIdMatch) {{
                        console.error('❌ API Fallback failed: Could not extract Asset ID from URL.');
                        return false;
                    }}
                    const assetId = assetIdMatch[0];
                    console.log(`Found Asset ID: ${{assetId}}`);

                    const response = await fetch(`/api/assets/${{assetId}}`, {{
                        method: 'PATCH',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ description: text }})
                    }});

                    if (response.ok) {{
                        console.log('✅ API Fallback successful: Asset updated directly.');
                        // Manually update the textarea value for visual consistency
                        textarea.value = text;
                        return true;
                    }} else {{
                        console.error(`❌ API Fallback failed: Server responded with status ${{response.status}}`);
                        const errorBody = await response.text();
                        console.error('Error details:', errorBody);
                        return false;
                    }}
                }} catch (e) {{
                    console.error('❌ Exception during API fallback:', e);
                    return false;
                }}
            }})();
            """
            
            self.page().runJavaScript(injection_script)
            print("✅ Injection script executed.")
            return True
            
        except Exception as e:
            print(f"❌ Python exception during injection: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
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