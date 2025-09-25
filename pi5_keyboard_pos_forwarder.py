#!/usr/bin/env python3
"""
Raspberry Pi 5 Keyboard POS Forwarder
Uses keyboard simulation since Pi 5 USB HID gadget mode is not readily available
"""

import subprocess
import time
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Pi5KeyboardPOSForwarder:
    def __init__(self):
        self.available_methods = self._detect_methods()
        logger.info("🍓 Pi 5 Keyboard POS Forwarder initialized")
        logger.info(f"🔧 Available methods: {', '.join(self.available_methods)}")
    
    def _detect_methods(self):
        methods = []
        
        # Check for xdotool (keyboard simulation)
        if self._command_exists('xdotool'):
            methods.append('KEYBOARD_SIM')
        
        # Check for clipboard tools
        if self._command_exists('xclip') or self._command_exists('xsel'):
            methods.append('CLIPBOARD')
        
        # Always available
        methods.append('ACTIVE_WINDOW')
        methods.append('FILE')
        
        return methods
    
    def _command_exists(self, command):
        try:
            subprocess.run(['which', command], capture_output=True, check=True)
            return True
        except:
            return False
    
    def forward_barcode_to_pos(self, barcode):
        """Forward barcode to POS terminal using keyboard simulation"""
        logger.info(f"🚀 Pi 5 forwarding barcode: {barcode}")
        
        # Try methods in order of preference for POS terminals
        methods = [
            ('ACTIVE_WINDOW', self._type_to_active_window),
            ('KEYBOARD_SIM', self._keyboard_simulation),
            ('CLIPBOARD', self._copy_to_clipboard),
            ('FILE', self._write_to_file)
        ]
        
        for method_name, method_func in methods:
            if method_name in self.available_methods:
                try:
                    logger.info(f"🔄 Trying {method_name}...")
                    success = method_func(barcode)
                    if success:
                        logger.info(f"✅ Pi 5 successfully forwarded via {method_name}")
                        return True
                    else:
                        logger.warning(f"⚠️  {method_name} failed, trying next...")
                except Exception as e:
                    logger.error(f"❌ {method_name} error: {e}")
        
        logger.error("❌ All Pi 5 forwarding methods failed")
        return False
    
    def _type_to_active_window(self, barcode):
        """Type barcode directly to the currently active window"""
        try:
            # Get active window info for debugging
            try:
                result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], 
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    window_name = result.stdout.strip()
                    logger.info(f"🎯 Active window: {window_name}")
            except:
                pass
            
            # Type the barcode with a slight delay between characters
            logger.info(f"⌨️  Typing barcode: {barcode}")
            subprocess.run(['xdotool', 'type', '--delay', '50', barcode], 
                         check=True, timeout=10)
            
            # Wait a moment then send Enter
            time.sleep(0.2)
            subprocess.run(['xdotool', 'key', 'Return'], 
                         check=True, timeout=5)
            
            logger.info("✅ Barcode typed to active window")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Keyboard typing timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Active window typing failed: {e}")
            return False
    
    def _keyboard_simulation(self, barcode):
        """Basic keyboard simulation"""
        try:
            # Simple keyboard simulation
            subprocess.run(['xdotool', 'type', barcode], 
                         timeout=5, check=True)
            subprocess.run(['xdotool', 'key', 'Return'], 
                         timeout=2, check=True)
            return True
        except Exception as e:
            logger.error(f"Keyboard simulation failed: {e}")
            return False
    
    def _copy_to_clipboard(self, barcode):
        """Copy barcode to clipboard"""
        try:
            # Try xclip first
            result = subprocess.run(['xclip', '-selection', 'clipboard'], 
                                  input=barcode.encode(), timeout=2)
            if result.returncode == 0:
                logger.info("📋 Copied to clipboard (xclip)")
                return True
        except:
            pass
        
        try:
            # Try xsel as fallback
            result = subprocess.run(['xsel', '--clipboard', '--input'], 
                                  input=barcode.encode(), timeout=2)
            if result.returncode == 0:
                logger.info("📋 Copied to clipboard (xsel)")
                return True
        except:
            pass
        
        return False
    
    def _write_to_file(self, barcode):
        """Write barcode to file as fallback"""
        try:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Write to multiple locations
            files = [
                '/tmp/pi5_pos_barcode.txt',
                '/tmp/current_barcode.txt'
            ]
            
            for file_path in files:
                with open(file_path, 'w') as f:
                    f.write(f"{timestamp}: {barcode}\n")
            
            logger.info("📄 Pi 5 barcode written to files")
            return True
        except Exception as e:
            logger.error(f"File writing failed: {e}")
            return False

def test_pi5_pos_forwarding():
    """Test Pi 5 POS forwarding with keyboard simulation"""
    print("🍓 Raspberry Pi 5 POS Forwarding Test")
    print("=" * 50)
    
    forwarder = Pi5KeyboardPOSForwarder()
    
    test_barcode = "8053734093444"
    print(f"\n🧪 Testing with barcode: {test_barcode}")
    print("💡 Make sure your POS terminal window is active/focused!")
    print("⏳ Starting in 3 seconds...")
    
    # Give user time to focus on POS terminal
    for i in range(3, 0, -1):
        print(f"   {i}...")
        time.sleep(1)
    
    print("🚀 Sending barcode now!")
    success = forwarder.forward_barcode_to_pos(test_barcode)
    
    if success:
        print(f"✅ Barcode {test_barcode} sent successfully!")
        print("💡 Check your POS terminal - the barcode should appear there")
    else:
        print(f"❌ Failed to send barcode {test_barcode}")
        print("💡 Try focusing on a text editor and run the test again")
    
    return success

if __name__ == "__main__":
    test_pi5_pos_forwarding()
