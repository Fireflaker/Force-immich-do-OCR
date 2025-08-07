#!/usr/bin/env python3
"""
Main Application for Immich OCR Browser
Modular, well-organized OCR browser with comprehensive automation.

ARCHITECTURE LESSONS LEARNED:
1. Modular design prevents 700+ line monoliths
2. Threading keeps UI responsive during OCR
3. Proper error handling prevents crashes
4. Centralized config makes changes easy
5. Background automation solves focus dependency
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QPushButton, QLineEdit, QLabel, QMenuBar, 
    QStatusBar, QMessageBox, QSplitter, QSpinBox, QToolBar
)
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon

# Import our modular components
from config import config
from web_engine import create_automation_web_view
from ocr_processor import OCRProcessor, qpixmap_to_pil
from focus_solutions import focus_manager
from ui_components import (
    PreviewDialog, SettingsDialog, StatusWidget,
    show_error_message, show_info_message, show_warning_message
)


class OCRWorkerThread(QThread):
    """Worker thread for OCR processing to keep UI responsive.
    
    LESSON: Never block the UI thread with OCR processing.
    Run OCR in background thread and signal completion.
    """
    
    ocr_completed = pyqtSignal(str, object)  # text, pixmap
    ocr_failed = pyqtSignal(str)  # error message
    
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.ocr_processor = OCRProcessor()
    
    def run(self):
        """Run OCR processing in background thread."""
        try:
            # Convert pixmap to PIL image
            pil_img = qpixmap_to_pil(self.pixmap)
            
            # Extract text
            text = self.ocr_processor.extract_text(pil_img)
            
            # Validate text quality
            is_valid, reason = self.ocr_processor.validate_text_quality(text)
            
            if is_valid:
                self.ocr_completed.emit(text, self.pixmap)
            else:
                self.ocr_failed.emit(reason)
                
        except Exception as e:
            self.ocr_failed.emit(f"OCR processing failed: {str(e)}")


class MainWindow(QMainWindow):
    """Main application window with modular components."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.ui.window_title)
        self.resize(*config.ui.default_window_size)
        
        # Initialize components
        self.ocr_processor = OCRProcessor()
        self.preview_dialog = PreviewDialog(self)
        self.settings_dialog = SettingsDialog(self)
        self.ocr_worker = None
        
        # Loop state
        self.loop_active = False
        self.loop_state = "OCR"  # "OCR" or "NAVIGATE"
        
        # Set up UI
        self._setup_ui()
        self._setup_menu()
        self._setup_connections()
        
        # Apply initial window settings
        self._apply_window_settings()
        
        # CRITICAL: Auto-load URL at launch (prevents empty page issue)
        # Use QTimer to ensure UI is fully initialized before loading
        # PITFALL: Loading too early causes UI race conditions
        # 500ms delay ensures all widgets are properly initialized
        QTimer.singleShot(500, self._auto_load_url)
    
    def _setup_ui(self):
        """Set up the main UI layout."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # URL input area
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        
        self.url_input = QLineEdit()
        self.url_input.setText("http://100.73.40.119:30041/")  # Default URL
        self.url_input.setPlaceholderText("Enter Immich URL (e.g., http://localhost:2283)")
        url_layout.addWidget(self.url_input)
        
        self.load_button = QPushButton("Load")
        self.load_button.clicked.connect(self._load_url)
        url_layout.addWidget(self.load_button)
        
        main_layout.addLayout(url_layout)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.crop_button = QPushButton("Select Crop Area")
        self.crop_button.clicked.connect(self._select_crop_area)
        self.crop_button.setEnabled(False)
        
        self.clear_button = QPushButton("Clear Selection")
        self.clear_button.clicked.connect(self._clear_crop)
        self.clear_button.setEnabled(False)
        
        self.ocr_button = QPushButton("Run OCR")
        self.ocr_button.clicked.connect(self._run_ocr)
        self.ocr_button.setEnabled(False)
        
        # Loop controls
        self.start_loop_button = QPushButton("Start Loop")
        self.start_loop_button.clicked.connect(self._start_loop)
        self.start_loop_button.setEnabled(False)
        
        self.stop_loop_button = QPushButton("Stop Loop")
        self.stop_loop_button.clicked.connect(self._stop_loop)
        self.stop_loop_button.setEnabled(False)
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._refresh_page)
        
        # Dual delay controls
        self.image_load_delay = QSpinBox()
        self.image_load_delay.setRange(500, 10000)  # 0.5-10 seconds
        self.image_load_delay.setValue(2000)  # 2 seconds default
        self.image_load_delay.setSuffix(" ms")
        
        self.description_save_delay = QSpinBox()
        self.description_save_delay.setRange(500, 10000)  # 0.5-10 seconds
        self.description_save_delay.setValue(1500)  # 1.5 seconds default
        self.description_save_delay.setSuffix(" ms")
        
        control_layout.addWidget(self.crop_button)
        control_layout.addWidget(self.clear_button)
        control_layout.addWidget(self.ocr_button)
        control_layout.addWidget(self.refresh_button)
        control_layout.addStretch()
        control_layout.addWidget(QLabel("Image Load:"))
        control_layout.addWidget(self.image_load_delay)
        control_layout.addWidget(QLabel("Save Delay:"))
        control_layout.addWidget(self.description_save_delay)
        control_layout.addWidget(self.start_loop_button)
        control_layout.addWidget(self.stop_loop_button)
        
        main_layout.addLayout(control_layout)
        
        # Create splitter for web view and crop preview
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Web view (main area)
        self.web_view = create_automation_web_view(self)
        splitter.addWidget(self.web_view)
        
        # Bottom area for crop preview and status
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        
        # Crop preview area
        crop_preview_layout = QVBoxLayout()
        crop_preview_layout.addWidget(QLabel("Crop Preview:"))
        
        self.crop_preview_label = QLabel()
        self.crop_preview_label.setMinimumSize(200, 100)
        self.crop_preview_label.setMaximumSize(400, 200)
        self.crop_preview_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.crop_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.crop_preview_label.setText("No crop selected")
        self.crop_preview_label.setScaledContents(True)
        crop_preview_layout.addWidget(self.crop_preview_label)
        
        bottom_layout.addLayout(crop_preview_layout)
        bottom_layout.addStretch()
        
        # Status widget
        self.status_widget = StatusWidget()
        self.status_widget.update_status("Ready - Load a URL to begin")
        bottom_layout.addWidget(self.status_widget)
        
        splitter.addWidget(bottom_widget)
        
        # Set splitter proportions (80% web view, 20% bottom)
        splitter.setSizes([800, 200])
        splitter.setCollapsible(0, False)  # Don't allow web view to collapse
        splitter.setCollapsible(1, True)   # Allow bottom panel to collapse
        
        main_layout.addWidget(splitter)
        
        # Make window properly resizable
        self.setMinimumSize(800, 600)
        self.resize(1400, 1000)  # Larger default size for better usability
    
    def _setup_menu(self):
        """Set up the application menu."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        preview_action = QAction("Show Preview", self)
        preview_action.triggered.connect(self.preview_dialog.show)
        view_menu.addAction(preview_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_connections(self):
        """Set up signal connections."""
        # Web view connections
        self.web_view.loadFinished.connect(self._on_page_loaded)
        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.crop_selected.connect(self._on_crop_selected)
        
        # Settings dialog connection
        self.settings_dialog.settings_changed.connect(self._on_settings_changed)
        
        # URL input connection
        self.url_input.returnPressed.connect(self._load_url)
    
    def _apply_window_settings(self):
        """Apply initial window settings."""
        # Center window on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def _load_url(self):
        """Load the specified URL."""
        url_text = self.url_input.text().strip()
        if not url_text:
            show_warning_message(self, "No URL", "Please enter a URL to load.")
            return
        
        # Add protocol if missing
        if not url_text.startswith(('http://', 'https://')):
            url_text = f"http://{url_text}"
        
        try:
            url = QUrl(url_text)
            self.web_view.load_with_automation(url)
            self.status_widget.update_status("Loading...")
            self.status_widget.update_url(url_text)
            
            # Update button states
            self.load_button.setEnabled(False)
            
        except Exception as e:
            show_error_message(self, "Load Error", f"Failed to load URL: {str(e)}")
    
    def _on_page_loaded(self, success: bool):
        """Handle page load completion."""
        if success:
            self.status_widget.update_status("Page loaded - Ready for OCR")
            self.crop_button.setEnabled(True)
            self.load_button.setEnabled(True)
        else:
            self.status_widget.update_status("Page load failed")
            show_error_message(self, "Load Failed", "Failed to load the webpage.")
            self.load_button.setEnabled(True)
    
    def _refresh_page(self):
        """Refresh the current page."""
        if hasattr(self.web_view, 'reload'):
            self.web_view.reload()
            self.status_widget.update_status("Refreshing page...")
        else:
            # Fallback: reload current URL
            current_url = self.web_view.url()
            if current_url.isValid():
                self.web_view.load(current_url)
                self.status_widget.update_status("Refreshing page...")
            else:
                show_warning_message(self, "Refresh Failed", "No valid URL to refresh.")
    
    def _auto_load_url(self):
        """Auto-load the default URL at launch to prevent empty page."""
        url_text = self.url_input.text().strip()
        if url_text:  # Only auto-load if there's a default URL
            self._load_url()
    
    def _on_url_changed(self, url: QUrl):
        """Handle URL changes."""
        self.status_widget.update_url(url.toString())
    
    def _on_crop_selected(self, rect):
        """Handle crop area selection and update preview."""
        self.clear_button.setEnabled(True)
        self.ocr_button.setEnabled(True)
        self.start_loop_button.setEnabled(True)
        self.status_widget.update_status(f"Crop area selected: {rect.width()}x{rect.height()}")
        
        # Update crop preview
        self._update_crop_preview()
    
    def _select_crop_area(self):
        """Enter crop selection mode."""
        self.web_view.start_crop_mode()
        self.status_widget.update_status("Crop mode active - Click and drag to select area")
        show_info_message(
            self, 
            "Crop Selection", 
            "Crop mode is now active!\n\n"
            "Click and drag on the webpage to select the area for OCR.\n"
            "The selected area will be highlighted with a red dashed border.\n"
            "Crop mode will automatically exit after selection."
        )
    
    def _clear_crop(self):
        """Clear the current crop selection."""
        self.web_view.clear_crop()
        self.clear_button.setEnabled(False)
        self.ocr_button.setEnabled(False)
        self.start_loop_button.setEnabled(False)
        self.status_widget.update_status("Crop selection cleared")
        
        # Clear crop preview
        self.crop_preview_label.clear()
        self.crop_preview_label.setText("No crop selected")
    
    def _update_crop_preview(self):
        """Update the crop preview with current selection."""
        crop_pixmap = self.web_view.capture_crop_area()
        if crop_pixmap and not crop_pixmap.isNull():
            # Scale pixmap to fit preview area
            scaled_pixmap = crop_pixmap.scaled(
                self.crop_preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.crop_preview_label.setPixmap(scaled_pixmap)
            self.crop_preview_label.setText("")  # Clear text when showing image
        else:
            self.crop_preview_label.setText("Preview failed")
    
    def _run_ocr(self):
        """Run OCR on the selected crop area.
        
        CRITICAL: OCR runs in separate thread to prevent UI freezing
        PITFALL: Never run OCR on main thread - blocks entire application
        """
        if not self.web_view.get_crop_rect():
            show_warning_message(self, "No Crop Area", "Please select a crop area first.")
            return
        
        # Capture the crop area
        crop_pixmap = self.web_view.capture_crop_area()
        if not crop_pixmap:
            show_error_message(self, "Capture Failed", "Failed to capture the crop area.")
            return
        
        # Update status
        self.status_widget.update_status("Processing OCR...")
        self.ocr_button.setEnabled(False)
        
        # Start OCR processing in background thread
        self.ocr_worker = OCRWorkerThread(crop_pixmap, self)
        self.ocr_worker.ocr_completed.connect(self._on_ocr_completed)
        self.ocr_worker.ocr_failed.connect(self._on_ocr_failed)
        self.ocr_worker.start()

    def _on_ocr_completed(self, text: str, pixmap):
        """Handle successful OCR completion."""
        self.status_widget.update_status("OCR completed - Injecting text...")
        
        # Show preview
        self.preview_dialog.update_content(pixmap, text)
        self.preview_dialog.show()
        
        # Inject text using automation
        success = self.web_view.inject_text_with_automation(text)
        
        if success:
            self.status_widget.update_status("Text injected successfully")
        else:
            self.status_widget.update_status("Text injection failed")
            show_error_message(
                self, 
                "Injection Failed", 
                "Failed to inject text into the webpage."
            )
        
        # Re-enable OCR button
        self.ocr_button.setEnabled(True)

    def _on_ocr_failed(self, error_message: str):
        """Handle OCR failure."""
        self.status_widget.update_status("OCR failed")
        show_error_message(self, "OCR Failed", error_message)
        self.ocr_button.setEnabled(True)
    
    def _on_crop_selected(self, rect):
        """Handle crop selection completion."""
        self.status_widget.update_status(f"Crop selected: {rect.width()}x{rect.height()}")
        self.crop_button.setEnabled(True)
        self.ocr_button.setEnabled(True)
    
    def _show_settings(self):
        """Show the settings dialog."""
        self.settings_dialog.show()
    
    def _on_settings_changed(self, new_settings: dict):
        """Handle settings changes."""
        self.status_widget.update_status("Settings updated")
        # Settings are automatically applied to the global config
    
    def _start_loop(self):
        """Start the OCR automation loop."""
        if self.loop_active:
            return
        
        if not self.web_view.get_crop_rect():
            show_warning_message(self, "No Crop Area", "Please select a crop area before starting the loop.")
            return
        
        self.loop_active = True
        self.loop_state = "OCR"
        
        # Update button states
        self.start_loop_button.setEnabled(False)
        self.stop_loop_button.setEnabled(True)
        self.ocr_button.setEnabled(False)
        self.crop_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.image_load_delay.setEnabled(False)
        self.description_save_delay.setEnabled(False)
        
        self.status_widget.update_status("Loop started - OCR and navigate automatically")
        self._automation_step()
    
    def _stop_loop(self):
        """Stop the OCR automation loop."""
        self.loop_active = False
        
        # Update button states
        self.start_loop_button.setEnabled(True)
        self.stop_loop_button.setEnabled(False)
        self.ocr_button.setEnabled(True)
        self.crop_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.image_load_delay.setEnabled(True)
        self.description_save_delay.setEnabled(True)
        
        self.status_widget.update_status("Loop stopped")
    
    def _automation_step(self):
        """Execute one step of the automation loop."""
        if not self.loop_active:
            return
        
        if self.loop_state == "OCR":
            self.status_widget.update_status("Loop: Running OCR...")
            self._run_ocr()
            self.loop_state = "WAIT_SAVE"
            # Use description save delay after OCR
            # CRITICAL: This delay allows time for text injection and saving
            save_delay = self.description_save_delay.value()
            QTimer.singleShot(save_delay, self._automation_step)
            
        elif self.loop_state == "WAIT_SAVE":
            self.loop_state = "NAVIGATE"
            # Short delay before navigation
            QTimer.singleShot(500, self._automation_step)
            
        elif self.loop_state == "NAVIGATE":
            self.status_widget.update_status("Loop: Navigating to next page...")
            self._navigate_next()
            self.loop_state = "WAIT_LOAD"
            # Use image load delay after navigation
            # CRITICAL: This delay allows time for new page/image to fully load
            load_delay = self.image_load_delay.value()
            QTimer.singleShot(load_delay, self._automation_step)
            
        elif self.loop_state == "WAIT_LOAD":
            self.loop_state = "OCR"
            # Ready for next OCR
            QTimer.singleShot(100, self._automation_step)
    
    def _navigate_next(self):
        """Navigate to the next page in Immich."""
        # Inject JavaScript to click the next arrow/button
        js_code = '''
        (function() {
            // Try multiple selectors for next button
            var selectors = [
                'button[aria-label*="next" i]',
                'button[title*="next" i]', 
                '[data-testid*="next"]',
                '.next-button',
                'button:contains("Next")',
                '[aria-label*="forward"]',
                'button svg[data-lucide="chevron-right"]'
            ];
            
            for (var selector of selectors) {
                var button = document.querySelector(selector);
                if (button && !button.disabled) {
                    button.click();
                    console.log('Clicked next button:', selector);
                    return true;
                }
            }
            
            // Try keyboard navigation
            document.dispatchEvent(new KeyboardEvent('keydown', {
                key: 'ArrowRight',
                keyCode: 39,
                which: 39,
                bubbles: true
            }));
            console.log('Used arrow key navigation');
            return true;
        })();
        '''
        
        self.web_view.page().runJavaScript(js_code)
    
    def _show_about(self):
        """Show the about dialog."""
        about_text = """
        <h3>Immich OCR Browser</h3>
        <p>A tool for automated OCR processing of images in Immich.</p>
        <p>Version: 1.0.0</p>
        <p>Features:</p>
        <ul>
            <li>Automated image capture and OCR processing</li>
            <li>Text injection into Immich description fields</li>
            <li>Persistent crop location memory</li>
            <li>Configurable delays and automation settings</li>
        </ul>
        """
        QMessageBox.about(self, "About", about_text)
    

    
    def mousePressEvent(self, event):
        """Handle mouse press events for crop selection."""
        # Update crop selection UI state
        if self.web_view.get_crop_rect():
            self.clear_button.setEnabled(True)
            self.ocr_button.setEnabled(True)
        super().mousePressEvent(event)
    
    def closeEvent(self, event):
        """Handle application close."""
        # Clean up worker thread if running
        if self.ocr_worker and self.ocr_worker.isRunning():
            self.ocr_worker.quit()
            self.ocr_worker.wait()
        
        event.accept()


def main():
    """Main application entry point."""
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName(config.ui.window_title)
    app.setApplicationVersion("3.0")
    
    # Set application icon if available
    try:
        app.setWindowIcon(QIcon("icon.png"))
    except:
        pass  # Icon file not found, continue without it
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()