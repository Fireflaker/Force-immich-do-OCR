    def _inject_text_and_save(self, text: str) -> bool:
        """
        Inject text into description field with comprehensive debug logging.
        
        CRITICAL: This method focuses on identifying WHERE the freeze occurs
        by providing extensive debug information at each step.
        """
        try:
            print(f"🔧 DEBUG: Starting text injection for: '{text}'")
            
            # Escape text for JavaScript
            text_escaped = text.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
            print(f"🔧 DEBUG: Escaped text: '{text_escaped}'")
            
            # Execute the comprehensive text injection script first
            print("🔧 DEBUG: Executing basic text injection script...")
            js = f"""
(function() {{
  console.log('📝 Basic text injection starting for: {text_escaped}');
  
  // Find all possible text elements
  var textareas = document.querySelectorAll('textarea');
  var textInputs = document.querySelectorAll('input[type="text"]');
  console.log('Found textareas:', textareas.length, 'text inputs:', textInputs.length);
  
  // Try to find description field
  var targets = [];
  textareas.forEach(function(ta) {{
    var placeholder = (ta.placeholder || '').toLowerCase();
    var name = (ta.name || '').toLowerCase();
    if (placeholder.includes('description') || name.includes('description')) {{
      targets.push({{ element: ta, type: 'description textarea' }});
    }} else {{
      targets.push({{ element: ta, type: 'general textarea' }});
    }}
  }});
  
  if (targets.length === 0) {{
    textInputs.forEach(function(inp) {{
      targets.push({{ element: inp, type: 'text input' }});
    }});
  }}
  
  console.log('Potential targets found:', targets.length);
  
  targets.forEach(function(target, index) {{
    var element = target.element;
    console.log('Processing target', index, ':', target.type);
    
    try {{
      element.focus();
      element.value = '{text_escaped}';
      element.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
      element.dispatchEvent(new Event('change', {{ bubbles: true, cancelable: true }}));
      console.log('Successfully updated', target.type, 'with value:', element.value);
    }} catch(e) {{
      console.error('Error updating', target.type, ':', e);
    }}
  }});
  
  console.log('✅ Basic injection completed');
}})();"""
            
            print("🔧 DEBUG: Executing basic JavaScript...")
            self.page().runJavaScript(js)
            print("🔧 DEBUG: Basic JavaScript executed successfully")
            
            # Now execute the debug-focused advanced script
            print("🔧 DEBUG: Executing advanced debug script...")
            debug_script = f"""
            console.log('🔧 DEBUG: Starting advanced debug script...');
            console.log('🔧 DEBUG: Current URL:', window.location.href);
            console.log('🔧 DEBUG: Document ready state:', document.readyState);
            console.log('🔧 DEBUG: Target text:', '{text_escaped}');
            
            try {{
                console.log('🔧 DEBUG: Step 1 - Looking for description field...');
                
                // Simple field detection with debug
                var field = document.querySelector('textarea[placeholder*="description" i]') || 
                           document.querySelector('textarea[name*="description" i]') ||
                           document.querySelector('textarea') ||
                           document.querySelector('input[type="text"]');
                
                if (!field) {{
                    console.error('❌ DEBUG: No field found');
                    var allTextareas = document.querySelectorAll('textarea');
                    var allInputs = document.querySelectorAll('input[type="text"]');
                    console.log('🔧 DEBUG: Available textareas:', allTextareas.length);
                    console.log('🔧 DEBUG: Available text inputs:', allInputs.length);
                    if (allTextareas.length > 0) {{
                        console.log('🔧 DEBUG: First textarea details:', allTextareas[0]);
                        field = allTextareas[0];
                    }}
                }}
                
                if (field) {{
                    console.log('✅ DEBUG: Field found:', field);
                    console.log('🔧 DEBUG: Field type:', field.tagName);
                    console.log('🔧 DEBUG: Field placeholder:', field.placeholder);
                    console.log('🔧 DEBUG: Field name:', field.name);
                    console.log('🔧 DEBUG: Field current value:', field.value);
                    
                    console.log('🔧 DEBUG: Step 2 - Setting field value...');
                    field.focus();
                    console.log('🔧 DEBUG: Field focused');
                    
                    field.value = '{text_escaped}';
                    console.log('🔧 DEBUG: Field value set to:', field.value);
                    
                    console.log('🔧 DEBUG: Step 3 - Dispatching events...');
                    field.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    console.log('🔧 DEBUG: Input event dispatched');
                    
                    field.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    console.log('🔧 DEBUG: Change event dispatched');
                    
                    console.log('🔧 DEBUG: Step 4 - Looking for asset ID...');
                    var assetIdMatch = window.location.href.match(/photos\/([a-f0-9-]{{36}})/);
                    var assetId = assetIdMatch ? assetIdMatch[1] : null;
                    console.log('🔧 DEBUG: Asset ID:', assetId);
                    
                    if (assetId) {{
                        console.log('🔧 DEBUG: Step 5 - Attempting API save...');
                        fetch('/api/assets/' + assetId, {{
                            method: 'PUT',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Accept': 'application/json'
                            }},
                            credentials: 'same-origin',
                            body: JSON.stringify({{ description: '{text_escaped}' }})
                        }})
                        .then(response => {{
                            console.log('🔧 DEBUG: API response status:', response.status);
                            console.log('🔧 DEBUG: API response ok:', response.ok);
                            return response.text();
                        }})
                        .then(text => {{
                            console.log('🔧 DEBUG: API response body:', text);
                        }})
                        .catch(error => {{
                            console.error('❌ DEBUG: API error:', error);
                        }});
                    }}
                    
                    console.log('✅ DEBUG: All steps completed successfully');
                }} else {{
                    console.error('❌ DEBUG: Still no field found after fallbacks');
                }}
                
            }} catch (error) {{
                console.error('❌ DEBUG: JavaScript error:', error);
                console.error('❌ DEBUG: Error stack:', error.stack);
            }}
            
            console.log('🔧 DEBUG: Script execution completed');
            """
            
            print("🔧 DEBUG: About to execute debug script...")
            self.page().runJavaScript(debug_script)
            print("🔧 DEBUG: Debug script executed successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ DEBUG: Python exception in _inject_text_and_save: {e}")
            print(f"❌ DEBUG: Exception type: {type(e)}")
            import traceback
            print(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")
            return False