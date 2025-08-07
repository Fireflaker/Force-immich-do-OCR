#!/usr/bin/env python3
"""
UI Components module for Immich OCR Browser
Provides reusable UI components and dialogs.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QScrollArea, QWidget,
    QMessageBox, QGroupBox, QFormLayout, QLineEdit,
    QSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont
from config import config


class PreviewDialog(QDialog):
    """Dialog for previewing OCR results and cropped images."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OCR Preview")
        self.resize(*config.ui.preview_dialog_size)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        
        # Image preview area
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        self.image_label.setMinimumHeight(300)
        
        # Scroll area for image
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # Text preview area
        text_group = QGroupBox("Extracted Text")
        text_layout = QVBoxLayout(text_group)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumHeight(150)
        
        # Use monospace font for better text readability
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_edit.setFont(font)
        
        text_layout.addWidget(self.text_edit)
        layout.addWidget(text_group)
        
        # Button area
        button_layout = QHBoxLayout()
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.hide)
        
        self.copy_button = QPushButton("Copy Text")
        self.copy_button.clicked.connect(self._copy_text_to_clipboard)
        
        button_layout.addStretch()
        button_layout.addWidget(self.copy_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
    
    def update_content(self, pixmap: QPixmap, text: str):
        """Update the preview content."""
        # Update image
        if pixmap and not pixmap.isNull():
            # Scale pixmap to fit label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setText("No image available")
        
        # Update text
        self.text_edit.setPlainText(text)
        
        # Enable/disable copy button based on text availability
        self.copy_button.setEnabled(bool(text.strip()))
    
    def _copy_text_to_clipboard(self):
        """Copy extracted text to clipboard."""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        
        # Show brief confirmation
        QMessageBox.information(self, "Copied", "Text copied to clipboard!")


class SettingsDialog(QDialog):
    """Dialog for application settings."""
    
    settings_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(400, 300)
        self.setModal(True)
        
        self._setup_ui()
        self._load_current_settings()
    
    def _setup_ui(self):
        """Set up the settings UI."""
        layout = QVBoxLayout(self)
        
        # OCR Settings
        ocr_group = QGroupBox("OCR Settings")
        ocr_layout = QFormLayout(ocr_group)
        
        self.tesseract_config_edit = QLineEdit()
        self.min_text_length_spin = QSpinBox()
        self.min_text_length_spin.setRange(1, 100)
        
        ocr_layout.addRow("Tesseract Config:", self.tesseract_config_edit)
        ocr_layout.addRow("Min Text Length:", self.min_text_length_spin)
        
        layout.addWidget(ocr_group)
        
        # Automation Settings
        automation_group = QGroupBox("Automation Settings")
        automation_layout = QFormLayout(automation_group)
        
        self.stealth_mode_check = QCheckBox()
        self.focus_override_check = QCheckBox()
        self.multi_save_check = QCheckBox()
        
        automation_layout.addRow("Stealth Mode:", self.stealth_mode_check)
        automation_layout.addRow("Focus Override:", self.focus_override_check)
        automation_layout.addRow("Multi-Save Attempts:", self.multi_save_check)
        
        layout.addWidget(automation_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.defaults_button = QPushButton("Restore Defaults")
        
        self.ok_button.clicked.connect(self._save_settings)
        self.cancel_button.clicked.connect(self.reject)
        self.defaults_button.clicked.connect(self._restore_defaults)
        
        button_layout.addWidget(self.defaults_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
    
    def _load_current_settings(self):
        """Load current settings into the UI."""
        # Load OCR settings
        self.tesseract_config_edit.setText(config.ocr.tesseract_config)
        self.min_text_length_spin.setValue(config.ocr.min_text_length)
        
        # Load automation settings
        self.stealth_mode_check.setChecked(config.automation.stealth_mode)
        self.focus_override_check.setChecked(config.automation.focus_override)
        self.multi_save_check.setChecked(config.automation.multi_save_attempts)
    
    def _save_settings(self):
        """Save settings and emit changes."""
        new_settings = {
            'ocr': {
                'tesseract_config': self.tesseract_config_edit.text(),
                'min_text_length': self.min_text_length_spin.value(),
            },
            'automation': {
                'stealth_mode': self.stealth_mode_check.isChecked(),
                'focus_override': self.focus_override_check.isChecked(),
                'multi_save_attempts': self.multi_save_check.isChecked(),
            }
        }
        
        # Update config
        config.ocr.tesseract_config = new_settings['ocr']['tesseract_config']
        config.ocr.min_text_length = new_settings['ocr']['min_text_length']
        config.automation.stealth_mode = new_settings['automation']['stealth_mode']
        config.automation.focus_override = new_settings['automation']['focus_override']
        config.automation.multi_save_attempts = new_settings['automation']['multi_save_attempts']
        
        self.settings_changed.emit(new_settings)
        self.accept()
    
    def _restore_defaults(self):
        """Restore default settings."""
        from config import OCRConfig, AutomationConfig
        
        # Create default configs
        default_ocr = OCRConfig()
        default_automation = AutomationConfig()
        
        # Update UI with defaults
        self.tesseract_config_edit.setText(default_ocr.tesseract_config)
        self.min_text_length_spin.setValue(default_ocr.min_text_length)
        self.stealth_mode_check.setChecked(default_automation.stealth_mode)
        self.focus_override_check.setChecked(default_automation.focus_override)
        self.multi_save_check.setChecked(default_automation.multi_save_attempts)


class StatusWidget(QWidget):
    """Widget for displaying application status."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the status UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.status_label = QLabel("Ready")
        self.url_label = QLabel("No URL loaded")
        
        layout.addWidget(QLabel("Status:"))
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.url_label)
    
    def update_status(self, status: str):
        """Update the status text."""
        self.status_label.setText(status)
    
    def update_url(self, url: str):
        """Update the URL display."""
        # Truncate long URLs
        if len(url) > 50:
            display_url = url[:47] + "..."
        else:
            display_url = url
        self.url_label.setText(display_url)


def show_error_message(parent, title: str, message: str):
    """Show an error message dialog."""
    QMessageBox.critical(parent, title, message)


def show_info_message(parent, title: str, message: str):
    """Show an information message dialog."""
    QMessageBox.information(parent, title, message)


def show_warning_message(parent, title: str, message: str):
    """Show a warning message dialog."""
    QMessageBox.warning(parent, title, message)