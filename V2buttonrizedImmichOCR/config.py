#!/usr/bin/env python3
"""
Configuration module for Immich OCR Browser
Centralizes all configuration settings and constants.

LESSON LEARNED: Centralized config prevents scattered hardcoded values.
All settings in one place = easy to modify and maintain.
Use dataclasses for type safety and clean organization.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class OCRConfig:
    """OCR processing configuration."""
    tesseract_config: str = "--psm 6"
    min_text_length: int = 3
    excluded_patterns: List[str] = None
    # Detection and mode tuning
    screenshot_sizes: List[tuple] = None  # list of (width, height)
    screenshot_aspect_ratios: List[float] = None  # e.g., 2.1667 (19.5:9), 2.2222 (20:9)
    aspect_ratio_tolerance: float = 0.02  # 2%
    psm_sparse: int = 11  # Tesseract PSM for sparse text
    psm_filled: int = 6   # Tesseract PSM for block/paragraph text
    
    def __post_init__(self):
        if self.excluded_patterns is None:
            self.excluded_patterns = ["NO USER", "CAPTCHA", "LOADING"]
        if self.screenshot_sizes is None:
            # Common Android/iOS screenshot sizes; extend as needed
            self.screenshot_sizes = [
                (1080, 2412), (2412, 1080),
                (720, 1608), (1608, 720),
                (1440, 3200), (3200, 1440),
                (1179, 2556), (2556, 1179),  # iPhone 15 Pro
                (1290, 2796), (2796, 1290),  # iPhone 15 Pro Max
                (1284, 2778), (2778, 1284),  # iPhone 12/13/14 Pro Max
                (1080, 2340), (2340, 1080),
            ]
        if self.screenshot_aspect_ratios is None:
            # Typical modern phone aspect ratios
            self.screenshot_aspect_ratios = [
                19.5/9, 20/9, 19.3/9, 19/9, 18.5/9, 16/9
            ]


@dataclass
class OCRLocationConfig:
    """OCR crop location persistence configuration."""
    # CRITICAL: Remember last OCR location between sessions
    # Prevents user from having to re-select crop area every launch
    remember_location: bool = True
    last_crop_x: int = 0
    last_crop_y: int = 0
    last_crop_width: int = 0
    last_crop_height: int = 0
    
    def save_location(self, x: int, y: int, width: int, height: int):
        """Save the current crop location for next session."""
        self.last_crop_x = x
        self.last_crop_y = y
        self.last_crop_width = width
        self.last_crop_height = height
        
    def has_saved_location(self) -> bool:
        """Check if there's a saved location to restore."""
        return (self.remember_location and 
                self.last_crop_width > 0 and 
                self.last_crop_height > 0)


@dataclass
class UIConfig:
    """UI configuration settings."""
    window_title: str = "Immich OCR Browser"
    default_window_size: tuple = (1200, 800)
    preview_dialog_size: tuple = (600, 700)
    crop_line_width: int = 2
    crop_line_color: str = "#FF0000"


@dataclass
class WebEngineConfig:
    """Web engine configuration."""
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    enable_dev_tools: bool = False
    disable_web_security: bool = True


@dataclass
class AutomationConfig:
    """Browser automation configuration."""
    stealth_mode: bool = True
    multi_save_attempts: bool = True
    focus_override: bool = True
    save_timeout_ms: int = 2000
    refocus_interval_ms: int = 50


class AppConfig:
    """Main application configuration manager."""
    
    def __init__(self):
        self.ocr = OCRConfig()
        self.ui = UIConfig()
        self.web_engine = WebEngineConfig()
        self.automation = AutomationConfig()
        self.ocr_location = OCRLocationConfig()  # NEW: OCR location memory
        
        # Application paths
        self.app_dir = Path(__file__).parent
        self.temp_dir = self.app_dir / "temp"
        self.logs_dir = self.app_dir / "logs"
        
        # Ensure directories exist
        self.temp_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
    
    def get_chrome_flags(self) -> List[str]:
        """Get Chrome automation flags for maximum reliability.
        
        CRITICAL: These flags disable browser security that blocks automation.
        Without these, background focus operations fail.
        """
        return [
            # CRITICAL AUTOMATION FLAGS - DO NOT REMOVE
        # WARNING: Each flag solves specific browser security blocking automation
        # Removing ANY flag will break background operation functionality
            '--enable-automation',
            '--disable-web-security',
            '--disable-blink-features=AutomationControlled',
            '--disable-features=VizDisplayCompositor',
            
            # FOCUS AND BACKGROUND OPERATION FLAGS - ADVANCED MULTI-INSTANCE SUPPORT
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows', 
            '--disable-renderer-backgrounding',
            '--disable-features=BackgroundFetch',
            '--disable-features=BlockInsecurePrivateNetworkRequests',
            '--disable-field-trial-config',  # Disable experiments that might affect focus
            '--force-fieldtrials=*BackgroundFetch/Disabled',  # Force disable background fetch
            '--disable-background-media-suspend',  # Prevent media suspension in background
            '--disable-features=RendererCodeIntegrity',  # Allow code injection for automation
            '--disable-features=VizServiceUsesGpuMemoryBufferResources',
            '--disable-features=VizHitTestDrawQuad',
            '--allow-legacy-extension-manifests',  # Support older extension APIs
            '--disable-features=IntenseWakeUpThrottling',  # Prevent timer throttling
            '--disable-features=NetworkService',  # Use legacy network stack for stability
            '--force-enable-metrics-reporting',  # Ensure focus events are reported
            
            # Security overrides for automation
            '--ignore-certificate-errors',
            '--ignore-ssl-errors',
            '--ignore-certificate-errors-spki-list',
            '--allow-running-insecure-content',
            '--disable-extensions',
            '--disable-plugins',
            
            # Window and process management
            '--disable-popup-blocking',
            '--disable-prompt-on-repost',
            '--disable-hang-monitor',
            '--disable-client-side-phishing-detection',
            '--disable-component-update',
            '--disable-default-apps',
            '--disable-dev-shm-usage',
            '--disable-device-discovery-notifications',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--no-default-browser-check',
            '--no-first-run',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            
            # MULTI-INSTANCE AND FOCUS INDEPENDENCE FLAGS
            '--disable-features=TabFreeze',  # Prevent tab freezing in background
            '--disable-features=CalculateNativeWinOcclusion',  # Disable window occlusion detection
            '--disable-features=WindowOcclusion',  # Disable window occlusion entirely  
            '--disable-features=UseOzonePlatform',  # Use legacy platform for stability
            '--force-app-mode',  # Run in app mode for better focus handling
            '--app-auto-launched',  # Mark as auto-launched for background operation
            '--enable-precise-memory-info',  # Better memory management for multiple instances
            '--disable-features=PaintHolding',  # Disable paint holding that can affect visibility
            '--disable-features=BackForwardCache',  # Disable cache that might interfere with navigation
            
            # Performance optimization
            '--memory-pressure-off',
            '--max_old_space_size=4096',
            '--disable-features=ScriptStreaming',
            '--disable-images',  # Improve performance
            
            # Audio/Video handling
            '--mute-audio',
            '--disable-audio-output',
            '--autoplay-policy=no-user-gesture-required',
            
            # Remote debugging (set to 0 to auto-assign port)
            '--remote-debugging-port=0',
            '--enable-logging=stderr',
            '--log-level=0',
            
            # Display and rendering  
            '--force-color-profile=srgb',
            # REMOVED: '--force-device-scale-factor=1',  # This breaks zoom functionality!
        # PITFALL: Never force device scale factor - breaks DPI handling and user zoom
            '--start-maximized',
            
            # RESEARCH-BASED FOCUS FLAGS (2024)
        # These solve the "focus dependency" problem where browser blocks operations
        # when window is not focused. CRITICAL for background automation.
            '--disable-features=UserMediaCaptureOnFocus',  # Disable focus requirement for media
            '--disable-field-trial-config',  # Disable A/B testing that might affect focus
            '--disable-background-mode',  # Prevent Chrome from running in background
            '--aggressive-cache-discard',  # Prevent interference from cache
        ]
    
    def get_javascript_selectors(self) -> Dict[str, str]:
        """Get CSS selectors for different web elements."""
        return {
            'description_textarea': 'textarea[data-testid="autogrow-textarea"]',
            'save_buttons': 'button[type="submit"]',
            'form_container': 'form',
        }


# Global configuration instance
config = AppConfig()