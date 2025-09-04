"""
LED Status Manager - Controls LED indicators based on device status
"""
import time
import threading
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class LEDStatusManager:
    """Manages LED indicators for device status"""
    
    # Status constants
    STATUS_OFFLINE = "offline"
    STATUS_CONNECTING = "connecting"
    STATUS_ONLINE = "online"
    STATUS_ERROR = "error"
    
    def __init__(self, gpio_available: bool = False):
        """Initialize the LED status manager"""
        self.gpio_available = gpio_available
        self.current_status = self.STATUS_OFFLINE
        self.blink_thread = None
        self.blink_active = False
        self.led_pins = {
            'red': 18,     # GPIO 18 (Pin 12)
            'yellow': 23,  # GPIO 23 (Pin 16)
            'green': 24    # GPIO 24 (Pin 18)
        }
        
        if self.gpio_available:
            self._setup_gpio()
        
    def _setup_gpio(self) -> None:
        """Initialize GPIO pins for LED control"""
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            self.GPIO.setmode(GPIO.BCM)
            
            # Set up all LED pins as outputs
            for pin in self.led_pins.values():
                self.GPIO.setup(pin, GPIO.OUT)
                self.GPIO.output(pin, GPIO.LOW)
                
            logger.info("✅ GPIO initialized for LED control")
            
        except Exception as e:
            self.gpio_available = False
            logger.warning(f"⚠️ Failed to initialize GPIO for LED control: {e}")
    
    def set_status(self, status: str) -> None:
        """
        Set the device status and update LEDs accordingly
        
        Args:
            status: One of the status constants (STATUS_OFFLINE, etc.)
        """
        if status == self.current_status:
            return
            
        logger.info(f"📶 Status changed: {self.current_status} → {status}")
        self.current_status = status
        
        # Stop any active blinking
        self._stop_blinking()
        
        # Set LEDs based on status
        if status == self.STATUS_OFFLINE:
            self._set_led('red', True)
            self._set_led('yellow', False)
            self._set_led('green', False)
            
        elif status == self.STATUS_CONNECTING:
            self._start_blinking('yellow')
            
        elif status == self.STATUS_ONLINE:
            self._stop_blinking()
            self._set_led('red', False)
            self._set_led('yellow', False)
            self._set_led('green', True)
            
        elif status == self.STATUS_ERROR:
            self._start_blinking('red')
    
    def _set_led(self, color: str, state: bool) -> None:
        """Set an LED on or off"""
        if not self.gpio_available:
            logger.debug(f"LED {color} {'ON' if state else 'OFF'}")
            return
            
        try:
            self.GPIO.output(self.led_pins[color], 
                           self.GPIO.HIGH if state else self.GPIO.LOW)
        except Exception as e:
            logger.error(f"Error setting LED {color}: {e}")
    
    def _start_blinking(self, color: str, interval: float = 0.5) -> None:
        """Start blinking an LED"""
        self._stop_blinking()
        self.blink_active = True
        self.blink_thread = threading.Thread(
            target=self._blink_worker,
            args=(color, interval),
            daemon=True
        )
        self.blink_thread.start()
    
    def _stop_blinking(self) -> None:
        """Stop any active blinking"""
        self.blink_active = False
        if self.blink_thread and self.blink_thread.is_alive():
            self.blink_thread.join(timeout=1.0)
        
        # Turn off all LEDs when stopping
        if self.gpio_available:
            for pin in self.led_pins.values():
                self.GPIO.output(pin, self.GPIO.LOW)
    
    def _blink_worker(self, color: str, interval: float) -> None:
        """Worker thread for blinking an LED"""
        try:
            while self.blink_active:
                self._set_led(color, True)
                time.sleep(interval)
                if not self.blink_active:
                    break
                self._set_led(color, False)
                time.sleep(interval)
        except Exception as e:
            logger.error(f"Error in blink worker: {e}")
    
    def cleanup(self) -> None:
        """Clean up GPIO resources"""
        self._stop_blinking()
        if self.gpio_available:
            try:
                self.GPIO.cleanup()
                logger.info("✅ GPIO cleanup complete")
            except Exception as e:
                logger.error(f"Error during GPIO cleanup: {e}")
