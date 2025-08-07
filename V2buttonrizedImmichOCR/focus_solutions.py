#!/usr/bin/env python3
"""
Focus Solutions module for Immich OCR Browser
Provides comprehensive JavaScript solutions for background automation.

CRITICAL: This module solves the "focus dependency" problem that plagued earlier versions.
- Browser security blocks focus() calls from background windows
- Multiple instances steal focus from each other
- Users couldn't multitask while OCR ran

Solution: 5-layer JavaScript approach that works WITHOUT requiring window focus.
"""

from typing import Dict
from config import config


class FocusSolutionManager:
    """Manages JavaScript solutions for background browser automation."""
    
    def __init__(self):
        self.config = config.automation
        self.selectors = config.get_javascript_selectors()
    
    def get_stealth_script(self) -> str:
        """
        Returns JavaScript to hide automation detection.
        
        LESSON LEARNED: Browsers detect automation and block operations.
        This script makes the browser think it's a real user.
        
        Returns:
            JavaScript code for stealth mode
        """
        return """
(function() {
    // SOLUTION 1: Enhanced Stealth Mode - Hide ALL automation detection
    
    // Kill webdriver detection
    delete window.navigator.webdriver;
    delete window.chrome?.runtime?.onConnect;
    
    // Override automation flags
    Object.defineProperty(navigator, 'webdriver', {
        get: () => false,
        configurable: true
    });
    
    // Spoof headless detection
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
        configurable: true
    });
    
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
        configurable: true
    });
    
    // Override console debug detection
    if (window.console && window.console.debug) {
        window.console.debug = () => {};
    }
    
    // Block automation detection scripts
    const originalEval = window.eval;
    window.eval = function(code) {
        if (typeof code === 'string' && code.includes('webdriver')) {
            return false;
        }
        return originalEval.apply(this, arguments);
    };
    
    console.log('Enhanced stealth mode activated');
})();
"""
    
    def get_focus_override_script(self) -> str:
        """
        Returns JavaScript to override focus detection.
        
        CRITICAL FIX: Browser checks document.hidden and hasFocus() before allowing events.
        This forces the browser to always report "focused" state.
        
        Returns:
            JavaScript code for focus override
        """
        return """
(function() {
    // SOLUTION 2: Comprehensive Focus Override - Based on latest research
    
    // Block ALL visibility change events (research-proven approach)
    const eventsToBlock = [
        'visibilitychange',
        'webkitvisibilitychange',
        'mozvisibilitychange',
        'msvisibilitychange',
        'blur',
        'focus',
        'hasFocus',
        'focusin',
        'focusout',
        'mouseleave',
        'mouseout'
    ];
    
    const eventHandler = (event) => {
        // CRITICAL: Only block events that are not on form elements
        // Allow ALL events on input/textarea elements for normal interaction
        if (event.target instanceof HTMLInputElement ||
            event.target instanceof HTMLTextAreaElement ||
            event.target instanceof HTMLSelectElement) {
            return; // Allow all events on form elements
        }
        
        // Check if target is inside a form (with safety check)
        if (event.target && typeof event.target.closest === 'function') {
            try {
                if (event.target.closest('form')) {
                    return; // Allow events on form containers
                }
            } catch (e) {
                // Ignore closest() errors
            }
        }
        
        // Only block window/document level events that interfere with automation
        if (event.type === 'visibilitychange' || 
            event.type.includes('visibility') ||
            (event.target === window || event.target === document)) {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
        }
    };
    
    // Block events on both window and document
    eventsToBlock.forEach(eventName => {
        window.addEventListener(eventName, eventHandler, true);
        document.addEventListener(eventName, eventHandler, true);
    });
    
    // Force always-visible state
    Object.defineProperty(document, 'hidden', {
        get: () => false,
        configurable: true
    });
    
    Object.defineProperty(document, 'visibilityState', {
        get: () => 'visible',
        configurable: true
    });
    
    Object.defineProperty(document, 'webkitVisibilityState', {
        get: () => 'visible',
        configurable: true
    });
    
    // Override ALL vendor-specific hidden properties
    ['mozHidden', 'msHidden', 'webkitHidden'].forEach(prop => {
        Object.defineProperty(document, prop, {
            get: () => false,
            configurable: true
        });
    });
    
    // Override hasFocus methods
    document.hasFocus = () => true;
    window.hasFocus = () => true;
    
    // Block blur/focus on window
    window.onblur = null;
    window.onfocus = () => true;
    window.blurred = false;
    
    // Override visibility change callbacks
    document.onvisibilitychange = null;
    
    console.log('Comprehensive focus override activated');
})();
"""
    
    def get_input_injection_script(self, text: str) -> str:
        """
        Returns comprehensive input injection script.
        
        Args:
            text: Text to inject into the textarea
            
        Returns:
            JavaScript code for advanced input simulation
        """
        # Sanitize text for JavaScript
        text_js = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
        selector = self.selectors['description_textarea']
        
        return f"""
(function(){{
  var ta = document.querySelector('{selector}');
  if(!ta) {{
    console.log('Textarea not found with selector: {selector}');
    return;
  }}
  
  // SOLUTION 3: Multi-method focus forcing
  function forceRealFocus(element) {{
    // Multiple focus attempts
    element.focus();
    element.click();
    if (element.select) element.select();
    
    // Force active element override
    Object.defineProperty(document, 'activeElement', {{
        get: function() {{ return element; }},
        configurable: true
    }});
    
    // Continuous refocus for reliability
    var refocusInterval = setInterval(function() {{
        if (document.activeElement !== element) {{
            element.focus();
        }}
    }}, {self.config.refocus_interval_ms});
    
    // Stop refocusing after timeout
    setTimeout(function() {{ 
        clearInterval(refocusInterval); 
    }}, {self.config.save_timeout_ms});
  }}
  
  // SOLUTION 4: Advanced input simulation
  function simulateRealInput(element, text) {{
    forceRealFocus(element);
    
    // Clear existing content with multiple methods
    element.value = '';
    if (element.textContent !== undefined) element.textContent = '';
    if (element.innerHTML !== undefined) element.innerHTML = '';
    
    // Set value using native property descriptor
    var nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype, 'value'
    ).set;
    nativeSetter.call(element, text);
    
    // Trigger comprehensive event sequence
    var events = ['focus', 'click', 'input', 'change', 'keydown', 'keyup', 'blur', 'focus'];
    events.forEach(function(eventType) {{
        var event = new Event(eventType, {{ 
            bubbles: true, 
            cancelable: true, 
            composed: true 
        }});
        element.dispatchEvent(event);
    }});
    
    console.log('Input simulation completed for text:', text.substring(0, 50) + '...');
  }}
  
  // SOLUTION 5: Multiple save mechanisms
  function executeAllSaveMethods(element) {{
    setTimeout(function() {{
        // Method 1: Ctrl+Enter on element
        var ctrlEnter = new KeyboardEvent('keydown', {{
            key: 'Enter', 
            code: 'Enter', 
            keyCode: 13, 
            which: 13,
            ctrlKey: true, 
            bubbles: true, 
            cancelable: true, 
            composed: true
        }});
        
        element.dispatchEvent(ctrlEnter);
        
        // Method 2: Ctrl+Enter on document
        document.dispatchEvent(ctrlEnter);
        
        // Method 3: Ctrl+Enter on window  
        window.dispatchEvent(ctrlEnter);
        
        // Method 4: Try form submission if textarea is in a form
        var form = element.closest('form');
        if (form) {{
            var submitEvent = new Event('submit', {{ 
                bubbles: true, 
                cancelable: true 
            }});
            form.dispatchEvent(submitEvent);
        }}
        
        // Method 5: Try clicking save buttons
        var saveSelectors = '{self.selectors['save_buttons']}';
        var saveButtons = document.querySelectorAll(saveSelectors);
        saveButtons.forEach(function(btn) {{ 
            btn.click(); 
        }});
        
        console.log('All save methods executed');
        
    }}, 100);
  }}
  
  // Execute the comprehensive input simulation
  simulateRealInput(ta, '{text_js}');
  executeAllSaveMethods(ta);
  
}})();
"""
    
    def get_complete_automation_script(self, text: str) -> str:
        """
        Returns complete automation script combining all solutions.
        
        Args:
            text: Text to inject
            
        Returns:
            Complete JavaScript automation code
        """
        if not self.config.stealth_mode:
            stealth = ""
        else:
            stealth = self.get_stealth_script()
        
        if not self.config.focus_override:
            focus_override = ""
        else:
            focus_override = self.get_focus_override_script()
        
        input_script = self.get_input_injection_script(text)
        
        return f"""
// === COMPREHENSIVE AUTOMATION SCRIPT ===
// WARNING: DO NOT REMOVE ANY OF THESE LAYERS!
// Each layer solves a specific browser security restriction.
// Removing any layer will break background automation.

{stealth}

{focus_override}

{input_script}

console.log('Complete automation script executed successfully');
// SUCCESS: All 5 layers applied - background operation should work
"""
    
    def apply_solutions(self, web_page, text: str) -> None:
        """
        Apply all focus solutions to a web page.
        
        Args:
            web_page: QWebEnginePage instance
            text: Text to inject
        """
        if self.config.stealth_mode:
            web_page.runJavaScript(self.get_stealth_script())
        
        if self.config.focus_override:
            web_page.runJavaScript(self.get_focus_override_script())
        
        # Apply main input injection with delay
        input_script = self.get_input_injection_script(text)
        web_page.runJavaScript(input_script)


# Global focus solution manager instance
focus_manager = FocusSolutionManager()