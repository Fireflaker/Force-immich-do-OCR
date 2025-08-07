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
import time
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QPushButton, QLineEdit, QLabel, QMenuBar, 
    QStatusBar, QMessageBox, QSplitter, QSpinBox, QToolBar, QCheckBox
)
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon

# Debug helper
def _dbg(msg: str):
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[DEBUG {ts}] {msg}")

# Import our modular components
from config import config
from web_engine import create_automation_web_view
from ocr_processor import OCRProcessor, qpixmap_to_pil
from focus_solutions import focus_manager
from ui_components import (
    SettingsDialog, StatusWidget,
    show_error_message, show_info_message, show_warning_message
)


class OCRWorkerThread(QThread):
    """Worker thread for OCR processing to keep UI responsive.
    
    LESSON: Never block the UI thread with OCR processing.
    Run OCR in background thread and signal completion.
    """
    
    ocr_completed = pyqtSignal(str, object)  # text, pixmap
    ocr_failed = pyqtSignal(str)  # error message
    
    def __init__(self, pixmap, full_page: bool = False, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.ocr_processor = OCRProcessor()
        # Adjust OCR parameters for full page mode (lower text ratio)
        if full_page:
            self.ocr_processor.config.min_text_length = max(1, self.ocr_processor.config.min_text_length // 2)
    
    def run(self):
        """Run OCR processing in background thread."""
        try:
            # Convert pixmap to PIL image
            pil_img = qpixmap_to_pil(self.pixmap)
            
            # Extract text
            text = self.ocr_processor.extract_text(pil_img)
            print(f"[DEBUG WORKER] OCR extracted text: {text[:80]}")
            
            # Validate text quality, but be more lenient in loop mode
            is_valid, reason = self.ocr_processor.validate_text_quality(text)
            
            # In loop mode:
            if self.parent().loop_active:
                if text.strip():
                    # Got some text, use it
                    self.ocr_completed.emit(text, self.pixmap)
                else:
                    # No text - emit special marker
                    self.ocr_completed.emit("USERNAME_OCR_FAIL", self.pixmap)
            # Not in loop - use normal validation
            elif is_valid:
                self.ocr_completed.emit(text, self.pixmap)
            else:
                self.ocr_failed.emit(reason)
                
        except Exception as e:
            if self.parent().loop_active:
                # In loop mode, use failure marker instead of error
                self.ocr_completed.emit("USERNAME_OCR_FAIL", self.pixmap)
            else:
                self.ocr_failed.emit(f"OCR processing failed: {str(e)}")


class MainWindow(QMainWindow):
    """Main application window with modular components."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.ui.window_title)
        self.resize(*config.ui.default_window_size)
        self.current_ocr_text = ""  # Track last OCR result for debug buttons
        
        # Initialize components
        self.ocr_processor = OCRProcessor()
        self.settings_dialog = SettingsDialog(self)
        self.ocr_worker = None
        # Track last OCR result to detect races
        self.current_ocr_text = ""
        
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
        
        # Test focus button for debugging
        self.test_focus_button = QPushButton("Test Focus")
        self.test_focus_button.clicked.connect(self._test_focus)
        self.test_focus_button.setEnabled(False)
        
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
        control_layout.addWidget(self.test_focus_button)
        control_layout.addStretch()
        control_layout.addWidget(QLabel("Image Load:"))
        control_layout.addWidget(self.image_load_delay)
        control_layout.addWidget(QLabel("Save Delay:"))
        control_layout.addWidget(self.description_save_delay)
        
        # Manual debug controls
        control_layout.addWidget(QLabel(" | Debug: "))
        self.debug_ocr = QPushButton("1. OCR")
        self.debug_ocr.clicked.connect(self._run_ocr)
        control_layout.addWidget(self.debug_ocr)
        
        self.debug_write = QPushButton("2. Write")
        self.debug_write.clicked.connect(self._do_write)
        control_layout.addWidget(self.debug_write)
        
        self.debug_next = QPushButton("3. Next")
        self.debug_next.clicked.connect(self._proceed_to_next)
        control_layout.addWidget(self.debug_next)
        
        # Full Page OCR toggle
        self.full_page_checkbox = QCheckBox("Full Page OCR")
        self.full_page_checkbox.setToolTip("Enable OCR on entire visible page instead of crop area")
        control_layout.addWidget(self.full_page_checkbox)
        control_layout.addWidget(self.start_loop_button)
        control_layout.addWidget(self.stop_loop_button)
        
        main_layout.addLayout(control_layout)
        
        # Create splitter for web view and crop preview
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Web view (main area)
        self.web_view = create_automation_web_view(self)
        splitter.addWidget(self.web_view)
        
        # Bottom area for crop preview, OCR result, and status
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
        
        # OCR result display
        ocr_result_layout = QVBoxLayout()
        ocr_result_layout.addWidget(QLabel("OCR Result:"))
        self.ocr_result_label = QLineEdit()  # Changed to QLineEdit for better text display
        self.ocr_result_label.setMinimumSize(200, 30)
        self.ocr_result_label.setReadOnly(True)
        self.ocr_result_label.setStyleSheet("""
            QLineEdit { 
                background-color: #f0f0f0;
                color: black;
                font-weight: bold;
                padding: 2px 5px;
                border: 1px solid #999;
            }
        """)
        self.ocr_result_label.setText("No OCR result")
        ocr_result_layout.addWidget(self.ocr_result_label)
        crop_preview_layout.addLayout(ocr_result_layout)
        
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
        self.web_view.cropSelectionFinished.connect(self._on_crop_selected)
        
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
            self.test_focus_button.setEnabled(True)
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
    
    def _test_focus(self):
        """Test focus functionality by writing a test message to the description field.
        
        This method:
        1. Uses the comprehensive focus_solutions approach 
        2. Focuses on the description field
        3. Writes a test message
        4. Triggers the save sequence
        5. Reports success/failure
        """
        _dbg("Test focus button clicked")
        
        try:
            # Test message
            test_text = f"Test focus message at {datetime.now().strftime('%H:%M:%S')}"
            
            _dbg(f"Attempting to inject test text: '{test_text}'")
            
            # Use the comprehensive focus manager approach
            success = self.web_view.inject_text_with_automation(test_text)
            
            if success:
                self.status_widget.update_status(f"✅ Test focus successful - Check description field")
                show_info_message(self, "Focus Test", f"Focus test completed!\n\nTest message: '{test_text}'\n\nCheck the description field and look for the 'updated' notification.")
            else:
                self.status_widget.update_status("❌ Test focus failed")
                show_error_message(self, "Focus Test Failed", "The focus test failed. Check the console for details.")
                
        except Exception as e:
            _dbg(f"Test focus exception: {e}")
            self.status_widget.update_status(f"❌ Test focus error: {str(e)}")
            show_error_message(self, "Focus Test Error", f"An error occurred during focus test:\n\n{str(e)}")
    
    def _run_ocr(self):
        """Run OCR on the selected crop area.
        
        CRITICAL: OCR runs in separate thread to prevent UI freezing
        PITFALL: Never run OCR on main thread - blocks entire application
        """
        _dbg(f"_run_ocr start | full_page={self.full_page_checkbox.isChecked()} | loop_state={self.loop_state} | last_text='{self.current_ocr_text}'")
        if (not self.full_page_checkbox.isChecked()) and (not self.web_view.get_crop_rect()):
            show_warning_message(self, "No Crop Area", "Please select a crop area first or enable Full Page OCR.")
            return
        
        # Capture the appropriate area
        if self.full_page_checkbox.isChecked():
            crop_pixmap = self.web_view.grab()
        else:
            crop_pixmap = self.web_view.capture_crop_area()
        if not crop_pixmap:
            show_error_message(self, "Capture Failed", "Failed to capture the crop area.")
            return
        
        # Update status
        self.status_widget.update_status("Processing OCR...")
        self.ocr_button.setEnabled(False)
        
        # Start OCR processing in background thread
        self.ocr_worker = OCRWorkerThread(crop_pixmap, full_page=self.full_page_checkbox.isChecked(), parent=self)
        self.ocr_worker.ocr_completed.connect(self._on_ocr_completed)
        self.ocr_worker.ocr_failed.connect(self._on_ocr_failed)
        self.ocr_worker.start()

    def _on_ocr_completed(self, text: str, pixmap):
        """Handle successful OCR completion."""
        # Store result and update UI
        self.current_ocr_text = text
        self.ocr_result_label.setText(text if text else "No text detected")
        self.status_widget.update_status("OCR completed - Ready to write")
        
        # Re-enable OCR button
        self.ocr_button.setEnabled(True)
        
        # Continue loop: OCR -> Write (with delay)
        if self.loop_active and text:
            _dbg(f"OCR completed in loop mode, scheduling write in {self.description_save_delay.value()}ms")
            self.status_widget.update_status("OCR completed - Writing text in loop...")
            QTimer.singleShot(self.description_save_delay.value(), self._loop_write_text)
        elif self.loop_active and not text:
            _dbg("OCR completed but no text detected, proceeding to next")
            self.status_widget.update_status("No text detected - Proceeding to next...")
            QTimer.singleShot(500, self._loop_proceed_to_next)
        
    def _do_write(self):
        """Write current OCR text to field."""
        if not self.current_ocr_text:
            self.status_widget.update_status("No OCR text to write")
            return
            
        def _after_injection(result):
            self.status_widget.update_status("Text written and saved")
            
        self.status_widget.update_status("Writing text to field...")
        self.web_view.inject_text_with_automation(self.current_ocr_text, finished_cb=_after_injection)

    def _proceed_to_next(self):
        """Navigate to next image - MANUAL button (simple version)."""
        _dbg("Manual next button clicked")
        self.status_widget.update_status("Navigating to next page...")

        # Clear any stored OCR result to prevent accidental write
        self.current_ocr_text = ""
        self.ocr_result_label.setText("No OCR result")

        # Navigate immediately (write operation already saves correctly)
        self._navigate_next()

        if self.loop_active:
            # Only schedule next OCR if in loop mode
            total_wait = self.image_load_delay.value() + 1000
            QTimer.singleShot(total_wait, self._automation_step)
    
    def _loop_write_text(self):
        """Write OCR text in loop mode - part of 3-step automation sequence."""
        if not self.loop_active:
            return
            
        _dbg(f"Loop step 2: Writing text: '{self.current_ocr_text[:50]}...'")
        self.status_widget.update_status("Loop: Writing OCR text...")
        
        def _after_write_injection(result):
            """Callback after text is written - proceed to navigation step."""
            _dbg(f"Text injection completed with result: {result}")
            self.status_widget.update_status("Loop: Text written and saved")

            # Continue loop: Write -> Navigate (save happens automatically now)
            if self.loop_active:
                self._loop_proceed_to_next()
        
        # Use our working automation to inject text
        if self.current_ocr_text:
            self.web_view.inject_text_with_automation(self.current_ocr_text, finished_cb=_after_write_injection)
        else:
            # No text to write, proceed to next
            _after_write_injection(True)
    
    def _loop_proceed_to_next(self):
        """Navigate to next image in loop mode - part of 3-step automation sequence."""
        if not self.loop_active:
            return
            
        _dbg("Loop step 3: Navigating to next image")
        self.status_widget.update_status("Loop: Navigating to next image...")
        
        # Clear OCR result for next cycle
        self.current_ocr_text = ""
        self.ocr_result_label.setText("No OCR result")
        
        # Navigate to next image
        self._navigate_next()
        
        # Continue loop: Navigate -> OCR (with image load delay)
        if self.loop_active:
            delay_ms = self.image_load_delay.value()
            _dbg(f"Scheduling next OCR cycle in {delay_ms}ms")
            self.status_widget.update_status(f"Loop: Waiting {delay_ms/1000:.1f}s for page load...")
            QTimer.singleShot(delay_ms, self._automation_step)

    def _on_ocr_failed(self, error_message: str):
        """Handle OCR failure by writing failure marker."""
        self.status_widget.update_status(f"OCR failed: {error_message}")
        self.ocr_result_label.setText("USERNAME_OCR_FAIL")
        self.current_ocr_text = "USERNAME_OCR_FAIL"
        
        # Re-enable OCR button
        self.ocr_button.setEnabled(True)
        
        # Continue loop: OCR Failed -> Write failure marker (with delay)
        if self.loop_active:
            _dbg(f"OCR failed in loop mode, scheduling failure write in {self.description_save_delay.value()}ms")
            self.status_widget.update_status("OCR failed - Writing failure marker in loop...")
            QTimer.singleShot(self.description_save_delay.value(), self._loop_write_text)
    
    def _on_crop_selected(self, rect):
        """Handle crop selection completion."""
        self.status_widget.update_status(f"Crop selected: {rect.width()}x{rect.height()}")
        # Enable relevant UI controls now that a crop area is available
        self.crop_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.ocr_button.setEnabled(True)
        self.start_loop_button.setEnabled(True)
        # Update the crop preview so the user can see the selection
        self._update_crop_preview()
    
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
        
        if (not self.full_page_checkbox.isChecked()) and (not self.web_view.get_crop_rect()):
            show_warning_message(self, "No Crop Area", "Please select a crop area before starting the loop or enable Full Page OCR.")
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
        """Execute step 1 of the 3-step automation loop: OCR.
        
        Complete automation sequence:
        1. OCR (this method) -> 2. Write Text -> 3. Navigate Next -> repeat
        """
        if not self.loop_active:
            return
            
        _dbg("Loop step 1: Starting OCR cycle")
        self.status_widget.update_status("Loop: Running OCR...")
        self._run_ocr()
    
    def _start_next_ocr_cycle(self):
        """Start a fresh OCR cycle after page load."""
        self.loop_state = "OCR"
        _dbg("Starting fresh OCR cycle")
        self._automation_step()

    def _navigate_next(self):
        """Navigate to the next asset in Immich using simple keyboard shortcut."""
        _dbg("_navigate_next invoked")

        # Simple approach: Use Immich's built-in keyboard shortcut (ArrowRight)
        # This is the most reliable method since it uses Immich's own navigation
        js_code = '''
        (function() {
            console.log('🎯 Using Immich keyboard shortcut for navigation...');

            // Focus the document first to ensure keyboard events work
            document.body.focus();

            // Use ArrowRight key (Immich's primary navigation shortcut)
            var arrowEvent = new KeyboardEvent('keydown', {
                key: 'ArrowRight',
                keyCode: 39,
                which: 39,
                bubbles: true,
                cancelable: true
            });
            document.dispatchEvent(arrowEvent);

            console.log('✅ Dispatched ArrowRight keyboard event for navigation');
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