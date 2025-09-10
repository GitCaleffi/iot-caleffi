import gradio as gr
import json
import os
import sys
from pathlib import Path
import logging
import time
import threading
import queue
import subprocess
import uuid
import requests
import re
import socket
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union
import hashlib
import uuid
from barcode_validator import validate_ean, BarcodeValidationError

# Camera-based barcode scanning imports
try:
    import cv2
    import numpy as np
    from pyzbar import pyzbar
    CAMERA_AVAILABLE = True
    print("✅ Camera barcode scanning libraries loaded successfully")
except ImportError as e:
    CAMERA_AVAILABLE = False
    print(f"⚠️ Camera barcode scanning not available: {e}")
    print("   Install with: pip install opencv-python pyzbar")

# ============================================================================
# CAMERA BARCODE SCANNING FUNCTIONS
# ============================================================================

def scan_barcode_from_camera(camera_index=0, timeout=30) -> Optional[str]:
    """Scan barcode from camera with timeout"""
    if not CAMERA_AVAILABLE:
        logger.error("❌ Camera libraries not available")
        return None
    
    try:
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            logger.error(f"❌ Cannot open camera {camera_index}")
            return None
        
        # Set camera properties
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        logger.info(f"📷 Camera scanning started - point camera at barcode (timeout: {timeout}s)")
        start_time = time.time()
        last_barcode = None
        stable_count = 0
        
        while time.time() - start_time < timeout:
            ret, frame = cap.read()
            if not ret:
                continue
            
            # Convert to grayscale for better detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect barcodes
            barcodes = pyzbar.decode(gray)
            
            for barcode in barcodes:
                barcode_data = barcode.data.decode('utf-8')
                
                # Require stable detection (same barcode detected multiple times)
                if barcode_data == last_barcode:
                    stable_count += 1
                    if stable_count >= 3:  # Stable detection
                        cap.release()
                        logger.info(f"✅ Barcode detected: {barcode_data}")
                        return barcode_data
                else:
                    last_barcode = barcode_data
                    stable_count = 1
            
            time.sleep(0.1)  # Small delay
        
        cap.release()
        logger.warning("⏰ Camera scanning timeout - no barcode detected")
        return None
        
    except Exception as e:
        logger.error(f"❌ Camera scanning error: {e}")
        return None

def scan_barcode_from_image(image_path: str) -> Optional[str]:
    """Scan barcode from image file"""
    if not CAMERA_AVAILABLE:
        logger.error("❌ Camera libraries not available")
        return None
    
    try:
        if not os.path.exists(image_path):
            logger.error(f"❌ Image file not found: {image_path}")
            return None
        
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"❌ Cannot read image: {image_path}")
            return None
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect barcodes
        barcodes = pyzbar.decode(gray)
        
        if barcodes:
            barcode_data = barcodes[0].data.decode('utf-8')
            logger.info(f"✅ Barcode found in image: {barcode_data}")
            return barcode_data
        else:
            logger.warning(f"❌ No barcode found in image: {image_path}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Image scanning error: {e}")
        return None

def start_camera_barcode_service():
    """Start automated camera-based barcode scanning service"""
    if not CAMERA_AVAILABLE:
        print("❌ Camera barcode scanning not available")
        print("   Install with: pip install opencv-python pyzbar")
        return
    
    logger.info("📷 Starting Camera-Based Barcode Scanner Service...")
    logger.info("🎯 Point camera at barcodes for automatic detection")
    logger.info("📡 All detected barcodes sent to both Frontend API and IoT Hub")
    logger.info("⏹️  Press Ctrl+C to stop the service")
    
    try:
        while True:
            print("\n📷 Starting camera scan (30 second timeout)...")
            print("🎯 Point your camera at a barcode...")
            
            # Scan barcode from camera
            barcode = scan_barcode_from_camera(timeout=30)
            
            if barcode and len(barcode) >= 6:
                logger.info(f"📊 Barcode detected: {barcode}")
                
                # Process the detected barcode
                result = process_barcode_scan_auto(barcode)
                
                if "✅" in result:
                    logger.info("✅ Barcode processed successfully")
                    print("✅ SUCCESS: Barcode sent to inventory system")
                else:
                    logger.warning("⚠️ Barcode processing had issues")
                    print("⚠️ WARNING: Check logs for details")
                    
                print(f"📊 Result: {result}")
                
            else:
                print("⏰ No barcode detected - trying again...")
                time.sleep(2)
                
    except KeyboardInterrupt:
        logger.info("🛑 Camera barcode service stopped by user")
        print("\n🛑 Camera service stopped. Thank you for using the barcode scanner!")

def generate_device_id() -> str:
    """Generate a unique device ID based on system information."""
    try:
        # Get system information
        hostname = socket.gethostname()
        mac = uuid.getnode()
        
        # Create a unique string from system info
        unique_str = f"{hostname}-{mac}"
        
        # Create a hash of the unique string
        device_id = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
        
        # Use first 12 characters of the hash
        return f"device-{device_id[:12]}"
        
    except Exception as e:
        logging.warning(f"Error generating device ID: {e}")
        return f"device-{str(uuid.uuid4())[:12]}"

GPIO_AVAILABLE = False
try:
    import platform
    import os
    
    is_pi = (
        os.path.exists('/proc/device-tree/model') and 
        'raspberry pi' in open('/proc/device-tree/model', 'r').read().lower()
    ) or (
        'arm' in platform.machine().lower() and 
        os.path.exists('/sys/firmware/devicetree/base/model')
    )
    
    if is_pi:
        import RPi.GPIO as GPIO
        GPIO_AVAILABLE = True
        print("✅ RPi.GPIO loaded successfully - LED functionality enabled")
    else:
        print("ℹ️ Not running on Raspberry Pi - LED functionality will use simulation mode")
        
except (ImportError, RuntimeError, FileNotFoundError) as e:
    GPIO_AVAILABLE = False
    print(f"ℹ️ RPi.GPIO not available: {e} - LED functionality will use simulation mode")


pi_status_thread = None
last_pi_status = None
pi_status_queue = queue.Queue()
pi_status_reporting_enabled = True
pi_status_lock = threading.Lock()

REGISTRATION_IN_PROGRESS = False
registration_lock = threading.Lock()
processed_device_ids = set()

def detect_lan_raspberry_pi() -> dict:
    """
    Detect Raspberry Pi devices on LAN using network discovery.
    Returns connection status and device information.
    """
    try:
        try:
            connection_manager = get_connection_manager()
            if connection_manager and connection_manager.is_connected_to_iot_hub:
                logger.info("✅ IoT Hub connected - starting registration instead of device discovery")
                try:
                    registration_service = get_dynamic_registration_service()
                    if registration_service:
                        registration_service.start_registration_process()
                except Exception as e:
                    logger.debug(f"Registration service not available: {e}")
                
                return {
                    'connected': True,
                    'ip': 'localhost',
                    'mac': 'local-device',
                    'hostname': 'iot-hub-connected',
                    'services': ['registration'],
                    'device_count': 1
                }
        except Exception as e:
            logger.debug(f"IoT connection check failed: {e}")
        
        from utils.network_discovery import NetworkDiscovery
        
        network_discovery = NetworkDiscovery()
        pi_devices = network_discovery.discover_raspberry_pi_devices()
        
        if pi_devices:
            primary_pi = pi_devices[0]  # Get first available Pi
            logger.info(f"✅ LAN Pi detected: {primary_pi.get('ip', 'unknown')} (MAC: {primary_pi.get('mac', 'unknown')})")
            return {
                'connected': True,
                'ip': primary_pi.get('ip'),
                'mac': primary_pi.get('mac'),
                'hostname': primary_pi.get('hostname', 'raspberry-pi'),
                'services': primary_pi.get('services', []),
                'device_count': len(pi_devices)
            }
        else:
            logger.info("❌ No Pi devices found on LAN during initial scan")
            return {
                'connected': False,
                'ip': None,
                'mac': None,
                'hostname': None,
                'services': [],
                'device_count': 0
            }
            
    except Exception as e:
        logger.error(f"Error detecting LAN Pi devices: {e}")
        return {
            'connected': False,
            'ip': None,
            'mac': None,
            'hostname': None,
            'services': [],
            'device_count': 0,
            'error': str(e)
        }

def send_pi_status_to_iot_hub(pi_status: dict, device_id: str = None) -> bool:
    """
    Send Raspberry Pi connection status to IoT Hub using Device Twin properties.
    This implements the 'twining technique' to report true/false Pi status.
    Only sends when Pi is actually connected (for connected=true) or when reporting disconnection.
    """
    try:
        from utils.dynamic_registration_service import get_dynamic_registration_service
        from iot.hub_client import HubClient
        from utils.connection_manager import ConnectionManager
        
        # Check real Pi connectivity before sending
        connection_manager = ConnectionManager()
        real_pi_connected = connection_manager.check_raspberry_pi_availability()
        
        # Only send if:
        # 1. Pi is actually connected and we're reporting connected=true, OR
        # 2. Pi is disconnected and we're reporting connected=false
        if pi_status['connected'] and not real_pi_connected:
            logger.warning("🚫 BLOCKING Pi status send - Pi shows connected but is actually disconnected")
            return False
        
        # Get device ID if not provided
        if not device_id:
            device_id = generate_device_id()
        
        # Get dynamic registration service
        registration_service = get_dynamic_registration_service()
        if not registration_service:
            logger.warning("⚠️ Dynamic registration service not available")
            return False
        
        # Get device connection string
        connection_string = registration_service.get_device_connection_string(device_id)
        if not connection_string:
            logger.warning(f"⚠️ No connection string for device {device_id}")
            return False
        
        # Create Device Twin properties payload
        twin_properties = {
            "pi_connection_status": {
                "connected": real_pi_connected,  # Use real connectivity status
                "ip_address": pi_status.get('ip'),
                "mac_address": pi_status.get('mac'),
                "hostname": pi_status.get('hostname'),
                "services_available": pi_status.get('services', []),
                "device_count": pi_status.get('device_count', 0),
                "last_check": datetime.now(timezone.utc).isoformat(),
                "detection_method": "real_time_check"
            }
        }
        
        # Send Device Twin update
        hub_client = HubClient(connection_string)
        if hub_client.connect():
            # Send as Device Twin reported properties
            success = hub_client.send_device_twin_update(twin_properties)
            if success:
                status_emoji = "✅" if real_pi_connected else "❌"
                logger.info(f"📡 Pi status sent to IoT Hub: Connected={real_pi_connected} {status_emoji}")
                return True
            else:
                logger.warning("⚠️ Failed to send Device Twin update")
                return False
        else:
            logger.warning("⚠️ Failed to connect to IoT Hub for Device Twin update")
            return False
            
    except Exception as e:
        logger.error(f"Error sending Pi status to IoT Hub: {e}")
        return False

def start_pi_status_monitoring():
    """
    Start background monitoring of Raspberry Pi LAN connection status.
    Sends periodic updates to IoT Hub about Pi connectivity.
    """
    global pi_status_thread, pi_status_reporting_enabled
    
    def pi_status_worker():
        """Background worker to monitor Pi status and report to IoT Hub"""
        logger.info("🔄 Pi status monitoring started (LAN detection + IoT Hub reporting)")
        
        last_status = None
        check_interval = 30  # Check every 30 seconds
        
        while pi_status_reporting_enabled:
            try:
                with pi_status_lock:
                    # Detect Pi on LAN
                    current_status = detect_lan_raspberry_pi()
                    
                    # Only send update if status changed or every 5 minutes
                    status_changed = (last_status is None or 
                                    last_status.get('connected') != current_status.get('connected'))
                    
                    if status_changed:
                        # Send status update to IoT Hub
                        device_id = generate_device_id()
                        success = send_pi_status_to_iot_hub(current_status, device_id)
                        
                        if success:
                            last_status = current_status.copy()
                            
                            # Log status change
                            if current_status['connected']:
                                logger.info(f"🟢 Pi CONNECTED on LAN: {current_status.get('ip', 'unknown IP')}")
                            else:
                                logger.info("🔴 Pi DISCONNECTED from LAN")
                        else:
                            logger.warning("⚠️ Failed to report Pi status to IoT Hub")
                    
                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Pi status monitoring error: {e}")
                time.sleep(60)  # Wait longer on error
    
    # Start monitoring thread
    if not pi_status_thread or not pi_status_thread.is_alive():
        pi_status_thread = threading.Thread(target=pi_status_worker, daemon=True)
        pi_status_thread.start()
        logger.info("📡 Pi status monitoring thread started")

def stop_pi_status_monitoring():
    """
    Stop the Pi status monitoring thread.
    """
    global pi_status_reporting_enabled
    pi_status_reporting_enabled = False
    logger.info("📡 Pi status monitoring stopped")

def is_pi_connected_for_scanning() -> tuple:
    """
    Check if Raspberry Pi is connected and ready for barcode scanning.
    Returns (is_connected: bool, status_message: str, pi_info: dict)
    """
    try:
        # Get current Pi status from LAN detection
        pi_status = detect_lan_raspberry_pi()
        
        if pi_status['connected']:
            pi_ip = pi_status.get('ip', 'unknown')
            services = pi_status.get('services', [])
            
            # Check if Pi has required services for scanning
            has_web_service = any('web' in str(service).lower() or '5000' in str(service) for service in services)
            has_ssh_service = any('ssh' in str(service).lower() or '22' in str(service) for service in services)
            
            if has_web_service or has_ssh_service:
                return True, f"✅ Pi ready for scanning at {pi_ip}", pi_status
            else:
                return False, f"⚠️ Pi found at {pi_ip} but services not available", pi_status
        else:
            return False, "❌ No Raspberry Pi detected on LAN", pi_status
            
    except Exception as e:
        logger.error(f"Error checking Pi connection for scanning: {e}")
        return False, f"❌ Pi connection check failed: {e}", {}

def test_lan_detection_and_iot_hub_flow():
    """
    Test the complete LAN detection and IoT Hub messaging flow.
    This function demonstrates the full workflow.
    """
    logger.info("🧪 Testing LAN detection and IoT Hub messaging flow...")
    
    try:
        # Step 1: Test LAN Pi detection
        logger.info("1️⃣ Testing LAN Pi detection...")
        pi_status = detect_lan_raspberry_pi()
        
        if pi_status['connected']:
            logger.info(f"✅ Pi detected on LAN: {pi_status.get('ip')} (MAC: {pi_status.get('mac')})")
        else:
            logger.info("❌ No Pi detected on LAN")
        
        # Step 2: Test IoT Hub status reporting
        logger.info("2️⃣ Testing IoT Hub status reporting...")
        device_id = generate_device_id()
        success = send_pi_status_to_iot_hub(pi_status, device_id)
        
        if success:
            logger.info("✅ Pi status successfully sent to IoT Hub via Device Twin")
        else:
            logger.warning("⚠️ Failed to send Pi status to IoT Hub")
        
        # Step 3: Test barcode scanning readiness
        logger.info("3️⃣ Testing barcode scanning readiness...")
        pi_connected, status_msg, pi_info = is_pi_connected_for_scanning()
        
        if pi_connected:
            logger.info(f"✅ System ready for barcode scanning: {status_msg}")
        else:
            logger.info(f"❌ System not ready for scanning: {status_msg}")
        
        # Step 4: Test complete workflow with sample barcode
        logger.info("4️⃣ Testing complete workflow with sample barcode...")
        test_result = process_barcode_scan("1234567890123", device_id)
        logger.info(f"📱 Barcode scan test result: {test_result[:100]}...")
        
        # Summary
        logger.info("🏁 Test Summary:")
        logger.info(f"   • LAN Detection: {'✅' if pi_status['connected'] else '❌'}")
        logger.info(f"   • IoT Hub Reporting: {'✅' if success else '❌'}")
        logger.info(f"   • Scanning Ready: {'✅' if pi_connected else '❌'}")
        logger.info(f"   • Device ID: {device_id}")
        
        return {
            'lan_detection': pi_status['connected'],
            'iot_hub_reporting': success,
            'scanning_ready': pi_connected,
            'device_id': device_id,
            'pi_info': pi_status
        }
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        return {
            'lan_detection': False,
            'iot_hub_reporting': False,
            'scanning_ready': False,
            'error': str(e)
        }

def get_local_mac_address() -> str:
    """Get the MAC address of the local device dynamically."""
    # Method 1: Use ip link command (most reliable for servers)
    try:
        result = subprocess.run(
            ["ip", "link", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            mac_pattern = r'link/ether ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
            matches = re.findall(mac_pattern, result.stdout.lower())
            for mac in matches:
                if mac != "00:00:00:00:00:00":
                    logger.info(f"📍 Found MAC address via ip link: {mac}")
                    return mac
    except Exception as e:
        logger.warning(f"ip link method failed: {e}")

    # Method 2: Use ifconfig command (fallback)
    try:
        result = subprocess.run(
            ["ifconfig"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            mac_pattern = r'ether ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
            matches = re.findall(mac_pattern, result.stdout.lower())
            for mac in matches:
                if mac != "00:00:00:00:00:00":
                    logger.info(f"📍 Found MAC address via ifconfig: {mac}")
                    return mac
    except Exception as e:
        logger.warning(f"ifconfig method failed: {e}")

    logger.error("❌ Could not detect local device MAC address using any method")
    return None

logger = logging.getLogger(__name__)

current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from utils.config import load_config, save_config
from iot.hub_client import HubClient
from database.local_storage import LocalStorage
from api.api_client import ApiClient
# FastBarcodeAPI is a separate FastAPI application - not imported here
from api.pi_device_notification import create_pi_notification_endpoint
from utils.dynamic_device_manager import device_manager
from utils.dynamic_registration_service import get_dynamic_registration_service
from utils.dynamic_device_id import generate_dynamic_device_id
from utils.network_discovery import NetworkDiscovery
from utils.connection_manager import ConnectionManager, get_connection_manager

from utils.mqtt_device_discovery import get_mqtt_discovery, discover_raspberry_pi_devices, get_primary_raspberry_pi_ip as mqtt_get_primary_pi_ip
# Removed auto IP detection - not needed for local MAC address mode

# Import IoT Hub registry manager for device registration
try:
    from azure.iot.hub import IoTHubRegistryManager
    from azure.iot.hub.models import DeviceCapabilities, AuthenticationMechanism, SymmetricKey, Device
    IOT_HUB_REGISTRY_AVAILABLE = True
except ImportError:
    logger.warning("Azure IoT Hub Registry Manager not available. Device registration will be limited.")
    IOT_HUB_REGISTRY_AVAILABLE = False

# Initialize database and API client
local_db = LocalStorage()
api_client = ApiClient()

# Offline simulation removed

# Track all processed device IDs, even those not saved in the database
processed_device_ids = set()

# Auto-registration function with IoT Hub integration
def auto_register_device_to_server():
    """Automatically register device with live server and IoT Hub using local MAC address"""
    try:
        mac_address = get_local_mac_address()
        if not mac_address:
            logger.error("❌ Cannot auto-register: MAC address not found")
            return False
            
        # Generate device ID from MAC address
        device_id = f"pi-{mac_address.replace(':', '')[-8:]}"
        
        # Check if already registered
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device.get('device_id') == device_id for device in registered_devices)
        
        if device_already_registered:
            logger.info(f"✅ Device {device_id} already registered - initializing IoT Hub connection")
            # Initialize IoT Hub connection for existing device
            _initialize_iot_hub_connection(device_id)
            return True
        
        # Get local IP address
        import socket
        try:
            # Connect to a remote server to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "127.0.0.1"
            
        logger.info(f"🚀 Auto-registering new device {device_id} (MAC: {mac_address}, IP: {local_ip})")
        
        # Step 1: Register with IoT Hub using dynamic registration service
        try:
            registration_service = get_dynamic_registration_service()
            token = device_manager.generate_registration_token()
            
            device_info = {
                "registration_method": "auto_plug_and_play",
                "mac_address": mac_address,
                "ip_address": local_ip,
                "auto_registered": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            success, message = device_manager.register_device(token, device_id, device_info)
            
            if success:
                logger.info(f"✅ Device {device_id} registered with IoT Hub successfully")
                
                # Save to local database
                local_db.save_device_id(device_id)
                
                # Initialize IoT Hub connection
                _initialize_iot_hub_connection(device_id)
                
                # Step 2: Register with live server API (optional)
                _register_with_live_server(device_id, mac_address, local_ip)
                
                return True
            else:
                logger.error(f"❌ IoT Hub registration failed: {message}")
                return False
                
        except Exception as e:
            logger.error(f"❌ IoT Hub registration error: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Auto-registration error: {e}")
        return False

def _initialize_iot_hub_connection(device_id):
    """Initialize IoT Hub connection for a registered device"""
    try:
        # Get device connection string from dynamic registration service
        device_connection_string = device_manager.get_device_connection_string(device_id)
        if device_connection_string:
            # Check Pi connectivity before sending to IoT Hub
            from utils.connection_manager import ConnectionManager
            connection_manager = ConnectionManager()
            
            if not connection_manager.check_raspberry_pi_availability():
                logger.warning("🚫 BLOCKING IoT Hub send - Pi device not connected")
                return True  # Registration saved locally, will send when Pi reconnects
            
            # Initialize IoT Hub client with device-specific connection string
            hub_client = HubClient(device_connection_string)
            
            # Send registration confirmation to IoT Hub
            confirmation_msg = {
                "deviceId": device_id,
                "status": "auto_registered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Device auto-registered via plug-and-play",
                "messageType": "device_registration"
            }
            
            hub_client.send_message(json.dumps(confirmation_msg), device_id)
            logger.info("📡 Registration confirmation sent to IoT Hub")
            
            # Send single heartbeat to IoT Hub (no background thread)
            _send_iot_hub_heartbeat(device_id, device_connection_string)
            
        else:
            logger.error(f"❌ Could not get device connection string for {device_id}")
            
    except Exception as e:
        logger.error(f"❌ IoT Hub connection initialization error: {e}")

def _register_with_live_server(device_id, mac_address, local_ip):
    """Register device with live server API (optional step)"""
    try:
        registration_data = {
            "device_id": device_id,
            "mac_address": mac_address,
            "ip_address": local_ip
        }
        
        # Send to live server - try multiple endpoints
        live_server_urls = [
            "http://localhost:5000/api/pi-device-register",  # Local web app first
            "https://iot.caleffionline.it/api/pi-device-register"  # Live server fallback
        ]
        
        # Try each URL until one works
        for url in live_server_urls:
            try:
                logger.info(f"Trying live server registration: {url}")
                response = requests.post(
                    url,
                    json=registration_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Device registered with live server: {url}")
                    
                    # Send single heartbeat to live server (no background thread)
                    heartbeat_url = url.replace('/api/pi-device-register', '/api/pi-device-heartbeat')
                    send_heartbeat_to_server(device_id, local_ip, heartbeat_url)
                    
                    return True
                else:
                    logger.warning(f"Live server registration failed for {url}: {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"Live server registration error for {url}: {e}")
                continue
        
        logger.warning("⚠️ Live server registration failed for all endpoints (IoT Hub registration still successful)")
        return False
        
    except Exception as e:
        logger.warning(f"⚠️ Live server registration error: {e}")
        return False

def _send_iot_hub_heartbeat(device_id, device_connection_string):
    """Send single heartbeat to IoT Hub (no loop)"""
    try:
        # Check Pi connectivity before sending heartbeat
        from utils.connection_manager import ConnectionManager
        connection_manager = ConnectionManager()
        
        if not connection_manager.check_raspberry_pi_availability():
            logger.warning("🚫 BLOCKING heartbeat send - Pi device not connected")
            return False
        
        hub_client = HubClient(device_connection_string)
        
        # Send heartbeat message
        heartbeat_message = {
            "deviceId": device_id,
            "messageType": "heartbeat",
            "timestamp": datetime.now().isoformat(),
            "status": "active"
        }
        
        hub_client.send_message(heartbeat_message)
        logger.info(f"💓 Heartbeat sent to IoT Hub for device: {device_id}")
        
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")

def is_raspberry_pi():
    """Check if the current system is a Raspberry Pi using multiple methods."""
    # Method 1: Check CPU info for ARM architecture (most reliable)
    try:
        with open('/proc/cpuinfo', 'r') as cpuinfo:
            content = cpuinfo.read().lower()
            # Check for ARM architecture indicators
            if any(indicator in content for indicator in ['arm', 'bcm', 'raspberry']):
                return True
            # If we see Intel/AMD, definitely not a Pi
            if any(vendor in content for vendor in ['genuineintel', 'authenticamd']):
                return False
    except Exception:
        pass

    # Method 2: Check the model file (modern Pis)
    try:
        with open('/sys/firmware/devicetree/base/model', 'r') as model_file:
            if 'raspberry pi' in model_file.read().lower():
                return True
    except Exception:
        pass
        
    # Method 3: Check the OS release info
    try:
        with open('/etc/os-release', 'r') as os_release:
            if 'raspbian' in os_release.read().lower():
                return True
    except Exception:
        pass

    # Method 4: Check hostname as last resort (unreliable but sometimes helpful)
    try:
        import socket
        hostname = socket.gethostname().lower()
        # Only use hostname if other methods are inconclusive AND it contains 'pi'
        # This is a weak indicator, so we're conservative
        if 'pi' in hostname:
            # But double-check we're not on Intel/AMD first
            with open('/proc/cpuinfo', 'r') as cpuinfo:
                if any(vendor in cpuinfo.read().lower() for vendor in ['genuineintel', 'authenticamd']):
                    return False
            # If no Intel/AMD detected and hostname suggests Pi, tentatively yes
            # But this is still unreliable
            return False  # Being conservative - hostname alone isn't enough
    except Exception:
        pass

    return False

IS_RASPBERRY_PI = is_raspberry_pi()

# GPIO LED Configuration
# ============================================================================
# LED CONTROL SYSTEM
# ============================================================================

class LEDController:
    """Control RGB LEDs on Raspberry Pi GPIO pins"""
    
    def __init__(self):
        self.gpio_available = GPIO_AVAILABLE and IS_RASPBERRY_PI
        self.led_pins = {
            'red': 18,     # GPIO 18 (Pin 12)
            'yellow': 23,  # GPIO 23 (Pin 16) 
            'green': 24    # GPIO 24 (Pin 18)
        }
        
        if self.gpio_available:
            self._setup_gpio()
            logger.info("🔴🟡🟢 GPIO LED controller initialized")
        else:
            logger.info("💡 LED controller in simulation mode (no GPIO)")
    
    def _setup_gpio(self):
        """Initialize GPIO pins for LED control"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            for color, pin in self.led_pins.items():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)  # Start with LEDs off
                
        except Exception as e:
            logger.error(f"GPIO setup failed: {e}")
            self.gpio_available = False
    
    def blink_led(self, color, duration=0.5, times=1):
        """Blink LED with specified color"""
        if not self.gpio_available:
            logger.info(f"💡 LED Blink: {color.upper()} ({'●' * times})")
            return
        
        try:
            pin = self.led_pins.get(color)
            if not pin:
                logger.warning(f"Unknown LED color: {color}")
                return
            
            for _ in range(times):
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(duration)
                GPIO.output(pin, GPIO.LOW)
                time.sleep(0.1)  # Short pause between blinks
                
        except Exception as e:
            logger.error(f"LED blink error: {e}")
    
    def set_led(self, color, state):
        """Set LED on/off state"""
        if not self.gpio_available:
            logger.info(f"💡 LED {color.upper()}: {'ON' if state else 'OFF'}")
            return
        
        try:
            pin = self.led_pins.get(color)
            if pin:
                GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
        except Exception as e:
            logger.error(f"LED control error: {e}")
    
    def cleanup(self):
        """Clean up GPIO resources"""
        if self.gpio_available:
            try:
                GPIO.cleanup()
                logger.info("🔌 GPIO cleanup completed")
            except Exception as e:
                logger.error(f"GPIO cleanup error: {e}")

# Global LED controller
led_controller = LEDController()

# Raspberry Pi Device Service Class
# ============================================================================
# RASPBERRY PI DEVICE SERVICE
# ============================================================================

class RaspberryPiDeviceService:
    """Raspberry Pi device service for direct Azure IoT Hub connection"""
    
    def __init__(self):
        self.device_id = None
        self.hub_client = None
        self.running = False
        self.network_connected = False
        self.barcode_queue = queue.Queue()
        self.scanner_thread = None
        self.network_monitor_thread = None
        self.heartbeat_thread = None
        
        logger.info("🆔 Initializing Raspberry Pi Device Service...")
        self._initialize_device()
        
    def _initialize_device(self):
        """Initialize Pi device with automatic registration and IoT Hub connection"""
        try:
            # Step 1: Generate device ID from MAC address
            mac_address = get_local_mac_address()
            if mac_address:
                self.device_id = f"pi-{mac_address.replace(':', '')[-8:]}"
                logger.info(f"🆔 Pi Device ID: {self.device_id}")
            else:
                self.device_id = f"pi-{uuid.uuid4().hex[:8]}"
                logger.warning(f"⚠️ Using fallback device ID: {self.device_id}")
            
            # Step 2: Check network connectivity (Wi-Fi/Ethernet)
            self._check_network_connectivity()
            
            # Step 3: Auto-register with Azure IoT Hub if connected
            if self.network_connected:
                self._register_with_iot_hub()
            else:
                logger.warning("⚠️ No network connection - will retry when network is available")
            
        except Exception as e:
            logger.error(f"❌ Device initialization failed: {e}")
    
    def _check_network_connectivity(self):
        """Check if Pi has network connectivity (Wi-Fi or Ethernet)"""
        try:
            # Test internet connectivity to Azure IoT Hub
            test_hosts = [
                ("CaleffiIoT.azure-devices.net", 443),  # Azure IoT Hub
                ("8.8.8.8", 53),  # Google DNS fallback
            ]
            
            for host, port in test_hosts:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    
                    if result == 0:
                        self.network_connected = True
                        logger.info(f"✅ Network connectivity confirmed to {host}:{port}")
                        
                        # Get network interface info
                        self._log_network_interfaces()
                        return True
                        
                except Exception as e:
                    logger.debug(f"Connection test failed for {host}:{port} - {e}")
                    continue
            
            self.network_connected = False
            logger.warning("❌ No network connectivity detected")
            return False
            
        except Exception as e:
            logger.error(f"Network connectivity check failed: {e}")
            self.network_connected = False
            return False
    
    def _log_network_interfaces(self):
        """Log available network interfaces (Wi-Fi/Ethernet)"""
        try:
            # Check network interfaces
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                active_interfaces = []
                
                for line in lines:
                    if 'state UP' in line:
                        interface = line.split(':')[1].strip()
                        active_interfaces.append(interface)
                
                if active_interfaces:
                    logger.info(f"🌐 Active network interfaces: {', '.join(active_interfaces)}")
                else:
                    logger.warning("⚠️ No active network interfaces found")
                    
        except Exception as e:
            logger.debug(f"Network interface check failed: {e}")
    
    def _register_with_iot_hub(self):
        """Register Pi device with Azure IoT Hub using device credentials"""
        try:
            logger.info(f"📡 Registering device {self.device_id} with Azure IoT Hub...")
            # Yellow LED: Registration in progress
            led_controller.blink_led('yellow', 0.5, 2)
            
            # Use dynamic registration service to get device connection string
            registration_service = get_dynamic_registration_service()
            token = device_manager.generate_registration_token()
            
            # Device info for registration
            device_info = {
                "registration_method": "pi_device_direct",
                "device_type": "raspberry_pi",
                "auto_registered": True,
                "network_interfaces": self._get_network_info(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Register device with IoT Hub
            success, message = device_manager.register_device(token, self.device_id, device_info)
            
            if success:
                logger.info(f"✅ Device {self.device_id} registered with Azure IoT Hub")
                # Green LED: Registration successful
                led_controller.blink_led('green', 0.5, 3)
                
                # Get device-specific connection string
                device_connection_string = device_manager.get_device_connection_string(self.device_id)
                
                if device_connection_string:
                    # Initialize IoT Hub client
                    self.hub_client = HubClient(device_connection_string)
                    logger.info("📡 Azure IoT Hub client initialized")
                    
                    # Send registration confirmation
                    self._send_registration_confirmation()
                    
                    # Start heartbeat service
                    self._start_heartbeat_service()
                    
                    return True
                else:
                    logger.error("❌ Failed to get device connection string")
                    # Red LED: Connection string failed
                    led_controller.blink_led('red', 0.3, 3)
                    return False
            else:
                logger.error(f"❌ IoT Hub registration failed: {message}")
                # Red LED: Registration failed
                led_controller.blink_led('red', 0.2, 5)
                return False
                
        except Exception as e:
            logger.error(f"❌ IoT Hub registration error: {e}")
            # Red LED: Registration error
            led_controller.blink_led('red', 0.1, 10)
            return False
    
    def _get_network_info(self):
        """Get current network configuration info"""
        try:
            network_info = {}
            
            # Get IP address
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                network_info['ip_address'] = s.getsockname()[0]
                s.close()
            except:
                network_info['ip_address'] = "unknown"
            
            # Get hostname
            network_info['hostname'] = socket.gethostname()
            
            return network_info
            
        except Exception as e:
            logger.debug(f"Network info collection failed: {e}")
            return {"ip_address": "unknown", "hostname": "unknown"}
    
    def _send_registration_confirmation(self):
        """Send registration confirmation message to IoT Hub"""
        try:
            confirmation_payload = {
                "deviceId": self.device_id,
                "messageType": "device_registration",
                "status": "registered",
                "deviceType": "raspberry_pi",
                "capabilities": ["barcode_scanning", "inventory_tracking"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "networkInfo": self._get_network_info()
            }
            
            success = self.hub_client.send_message(json.dumps(confirmation_payload), self.device_id)
            
            if success:
                logger.info("📡 Registration confirmation sent to IoT Hub")
            else:
                logger.warning("⚠️ Failed to send registration confirmation")
        except Exception as e:
            logger.warning(f"Registration confirmation error: {e}")
    
    def _start_heartbeat_service(self):
        """Send single heartbeat (no background service)"""
        try:
            if self.hub_client and self.network_connected:
                heartbeat_payload = {
                    "deviceId": self.device_id,
                    "messageType": "heartbeat",
                    "status": "online",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "networkInfo": self._get_network_info()
                }
                
                self.hub_client.send_message(json.dumps(heartbeat_payload), self.device_id)
                logger.info(f"💓 Single heartbeat sent to IoT Hub for device: {self.device_id}")
                
        except Exception as e:
            logger.warning(f"Heartbeat error: {e}")
        
        logger.info("💓 Heartbeat service disabled (no background threads)")
    
    def start_barcode_scanning_service(self):
        """Start the barcode scanning service (no background threads)"""
        try:
            logger.info("📱 Starting barcode scanning service...")
            self.running = True
            
            # Perform single network check instead of background monitoring
            self._network_monitor_worker()
            
            logger.info("✅ Barcode scanning service started")
            logger.info("📱 Ready to scan barcodes - data will be sent to Azure IoT Hub")
            logger.info("🚫 Background threads disabled for stability")
            
        except Exception as e:
            logger.error(f"Failed to start barcode scanning service: {e}")
    
    def _network_monitor_worker(self):
        """Single network connectivity check (no background loop)"""
        try:
            # Check network connectivity once
            previous_status = self.network_connected
            self._check_network_connectivity()
            
            # If network was restored, try to reconnect to IoT Hub
            if not previous_status and self.network_connected:
                logger.info("🌐 Network connectivity restored - reconnecting to IoT Hub")
                if not self.hub_client:
                    self._register_with_iot_hub()
            
            # If network was lost, log the status
            elif previous_status and not self.network_connected:
                logger.warning("⚠️ Network connectivity lost - barcodes will be stored locally")
            
        except Exception as e:
            logger.error(f"Network monitoring error: {e}")
    
    def stop(self):
        """Stop the barcode scanning service"""
        logger.info("🛑 Stopping Raspberry Pi Device Service...")
        self.running = False
        # Red LED: Service stopping
        led_controller.blink_led('red', 0.2, 3)
        led_controller.cleanup()

# Global Pi device service instance
pi_device_service = None

# ============================================================================
# SCANNER AND NETWORK FUNCTIONS
# ============================================================================

def is_scanner_connected():
    """Check if USB barcode scanner is connected"""
    try:
        if IS_RASPBERRY_PI:
            # On Pi, check for actual USB scanner
            command = "grep -E -i 'scanner|barcode|keyboard' /sys/class/input/event*/device/name"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return result.returncode == 0 and result.stdout
        else:
            # On server, assume virtual scanner
            return True
    except Exception as e:
        logger.error(f"Scanner check error: {e}")
        return True

def get_primary_raspberry_pi_ip():
    """
    Get the primary Raspberry Pi IP address using dynamic discovery.
    Returns the IP of the first Pi device found with web services available.
    
    Returns:
        str: IP address of primary Pi device, or None if not found
    """
    try:
        config = load_config()
        raspberry_pi_config = config.get("raspberry_pi", {})
        
        # Check if dynamic discovery is enabled
        if raspberry_pi_config.get("dynamic_discovery", False):
            # Use dynamic discovery system
            from utils.dynamic_pi_discovery import DynamicPiDiscovery
            
            dynamic_discovery = DynamicPiDiscovery(config)
            current_devices = dynamic_discovery.get_current_devices()
            
            if current_devices:
                # Return first device with web services
                for device in current_devices:
                    if 'web' in device.get('services', []):
                        logger.info(f"🔍 Dynamic discovery found Pi with web service: {device['ip']}")
                        return device['ip']
                
                # Fallback to first device
                first_device = current_devices[0]
                logger.info(f"🔍 Dynamic discovery found Pi: {first_device['ip']}")
                return first_device['ip']
            
            # Force a scan if no devices found
            logger.info("🔍 No devices found, forcing scan...")
            scan_results = dynamic_discovery.force_scan()
            if scan_results:
                first_device = scan_results[0]
                logger.info(f"🔍 Force scan found Pi: {first_device['ip']}")
                return first_device['ip']
        
        # Check for auto-detected IP from previous discoveries
        auto_detected_ip = raspberry_pi_config.get("auto_detected_ip")
        if auto_detected_ip:
            logger.info(f"📍 Using auto-detected Pi IP: {auto_detected_ip}")
            return auto_detected_ip
        
        # Fallback to manual IP if configured
        if raspberry_pi_config.get("use_manual_ip", False):
            manual_ip = raspberry_pi_config.get("manual_ip")
            if manual_ip:
                logger.info(f"📍 Using manual Pi IP from config: {manual_ip}")
                return manual_ip
        
        # Final fallback to network discovery
        from utils.network_discovery import NetworkDiscovery
        discovery = NetworkDiscovery()
        devices = discovery.discover_raspberry_pi_devices()
        
        if devices:
            primary_device = devices[0]
            logger.info(f"✅ Network discovery found Pi: {primary_device['ip']}")
            return primary_device['ip']
        
        logger.warning("❌ No Pi devices found via any discovery method")
        return None
        
    except Exception as e:
        logger.error(f"Error discovering Pi devices: {e}")
        return None


# ============================================================================
# PI CONNECTION MANAGEMENT
# ============================================================================

# Global variable to track Pi connection status (no caching)
_pi_connection_status = {
    'connected': False,
    'ip': None,
    'last_check': None
}


def check_raspberry_pi_connection():
    """
    Real-time Raspberry Pi device connectivity check.
    Directly checks if Pi device is connected without caching.
    
    Returns:
        bool: True if Pi device is connected and responsive, False otherwise
    """
    try:
        logger.debug("🔍 Checking real-time Pi device connectivity...")
        
        # Use connection manager for direct Pi device check
        from utils.connection_manager import ConnectionManager
        connection_manager = ConnectionManager()
        
        # Direct Pi availability check - no caching
        pi_connected = connection_manager.check_raspberry_pi_availability()
        
        if pi_connected:
            logger.info("✅ Pi device CONNECTED and responsive")
            return True
        else:
            logger.info("❌ Pi device DISCONNECTED or not responsive")
            return False
            
    except Exception as e:
        logger.error(f"Error checking Pi connectivity: {e}")
        return False

def _update_pi_status(connected, ip=None):
    """Update the Pi connection status cache"""
    global _pi_connection_status
    _pi_connection_status.update({
        'connected': connected,
        'ip': ip,
        'last_check': datetime.now(),
        'ssh_available': False,
        'web_available': False
    })

def _check_pi_on_lan():
    """Check for Pi on local network with improved error handling"""
    try:
        # Try network discovery for external Pi devices
        logger.info("🔍 Searching for Raspberry Pi on local network...")
        
        # Get connection manager
        connection_manager = ConnectionManager()
        if not connection_manager:
            logger.error("Connection manager not available")
            _update_pi_status(False)
            return False
            
        # Check Pi availability through connection manager
        pi_available = connection_manager.check_raspberry_pi_availability()
        
        if not pi_available:
            logger.info("ℹ️ No Raspberry Pi found on local network")
            _update_pi_status(False)
            return False
            
        # Try to get Pi IP from discovery
        try:
            pi_ip = get_primary_raspberry_pi_ip()
            if pi_ip:
                logger.info(f"✅ Found Raspberry Pi at: {pi_ip}")
                _update_pi_status(True, pi_ip)
                
                # Update config with discovered IP
                try:
                    config = load_config()
                    if config:
                        pi_config = config.get('raspberry_pi', {})
                        if pi_config.get('auto_detected_ip') != pi_ip:
                            pi_config['auto_detected_ip'] = pi_ip
                            pi_config['last_detection'] = datetime.now(timezone.utc).isoformat()
                            config['raspberry_pi'] = pi_config
                            save_config(config)
                            logger.info(f"💾 Updated config with Pi IP: {pi_ip}")
                except Exception as e:
                    logger.warning(f"Config update failed: {e}")
                    
                return True
                
        except Exception as e:
            logger.warning(f"Error getting Pi IP: {e}")
            
    except Exception as e:
        logger.error(f"Error during Pi LAN discovery: {e}")
    
    _update_pi_status(False)
    return False






# ============================================================================
# UI WRAPPER FUNCTIONS
# ============================================================================

# UI wrapper for processing unsent messages with progress
def process_unsent_messages_ui():
    """Process unsent messages with user-visible progress for Gradio UI."""
    # Check if Raspberry Pi is connected using connection manager for consistency
    from utils.connection_manager import ConnectionManager
    connection_manager =  ConnectionManager()
    pi_available = connection_manager.check_raspberry_pi_availability()
    
    if not pi_available:
        logger.warning("Process unsent messages blocked: Raspberry Pi not connected")
        led_controller.blink_led("red")
        return """❌ **Operation Failed: Raspberry Pi Not Connected**

Cannot process unsent messages while Raspberry Pi is offline.
Messages will remain in local database until Pi reconnects.
Please ensure the Raspberry Pi device is connected and reachable on the network.

🔴 Red LED indicates Pi connection failure"""
    
    logger.info("Processing unsent messages with Pi connection verified")
    
    # Initial loading message so the user sees a loader immediately
    yield "⏳ Processing unsent messages to IoT Hub... Please wait."
    try:
        result = process_unsent_messages(auto_retry=False)
        yield "✅ Finished processing unsent messages.\n\n" + (result or "")
    except Exception as e:
        error_msg = f"❌ Error while processing unsent messages: {str(e)}"
        logger.error(error_msg)
        yield error_msg

# Offline simulation logic removed



# ============================================================================
# DEVICE REGISTRATION FUNCTIONS
# ============================================================================

def generate_registration_token():
    """Prepare for device registration (no token required)"""
    
    # Check Raspberry Pi connection first using connection manager
    from utils.connection_manager import ConnectionManager
    connection_manager = ConnectionManager()
    pi_available = connection_manager.check_raspberry_pi_availability()
    
    logger.info(f"🔍 Pi availability check result: {pi_available}")
    
    # Always show current status, but block registration if Pi not available
    scanner_connected = is_scanner_connected()
    
    try:
        # Get real-time status for display
        pi_status = "Connected ✅" if pi_available else "Disconnected ❌"
        scanner_status = "Connected ✅" if scanner_connected else "Disconnected ❌"
        
        if not pi_available:
            # Show status but indicate registration is blocked
            response_msg = f"""❌ **Device Registration Blocked: Raspberry Pi Not Connected**

**Pi Status:** {pi_status}
**Scanner Status:** {scanner_status}

**Error:** Cannot proceed with device registration while Raspberry Pi is offline.

**Instructions:**
1. Connect your Raspberry Pi to ethernet/wifi
2. Wait for Pi Status to show "Connected ✅"
3. Try registration again

Please ensure the Raspberry Pi device is connected and reachable on the network."""
            
            logger.warning("Device registration blocked: Raspberry Pi not connected")
            led_controller.blink_led("red")
            return response_msg
        
        if not scanner_connected:
            response_msg = f"""⚠️ **Scanner Not Detected**

**Pi Status:** {pi_status}
**Scanner Status:** {scanner_status}

Please connect your barcode scanner device and try again."""
            return response_msg
        
        response_msg = f"""✅ Ready for Device Registration!

**Pi Status:** {pi_status}
**Scanner Status:** {scanner_status}

**Instructions:**
1. Enter your desired Device ID in the field below
2. Click 'Confirm Registration' to complete the process
3. No registration token required!

**Note:** Device registration is now simplified - just enter a unique Device ID and confirm."""
        
        led_controller.blink_led("green")
        return response_msg
        
    except Exception as e:
        logger.error(f"Error preparing registration: {str(e)}")
        led_controller.blink_led("red")
        return f"❌ Error: {str(e)}"

def register_device_id(barcode):
    """Step 1: Scan test barcode on registered device, hit API twice, send response to frontend"""
    try:
        # Only allow the test barcode for registration
        if barcode != "817994ccfe14":
            led_controller.blink_led("red")
            return "❌ Only the test barcode (817994ccfe14) can be used for registration."
        
        is_online = api_client.is_online()
        if not is_online:
            led_controller.blink_led("red")
            return "❌ Device is offline. Cannot register device."
        
        api_url_1 = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        payload_1 = {"scannedBarcode": barcode}
        
        logger.info(f"Making first API call to {api_url_1}")
        api_result_1 = api_client.send_registration_barcode(api_url_1, payload_1)
        
        if not api_result_1.get("success", False):
            led_controller.blink_led("red")
            return f"❌ First API call failed: {api_result_1.get('message', 'Unknown error')}"
        
        logger.info(f"Making second API call to {api_url_1}")
        api_result_2 = api_client.send_registration_barcode(api_url_1, payload_1)
        
        if not api_result_2.get("success", False):
            led_controller.blink_led("red")
            return f"❌ Second API call failed: {api_result_2.get('message', 'Unknown error')}"
        
        # Save test barcode scan locally (but not device ID yet - that happens in confirmation)
        local_db.save_test_barcode_scan(barcode)
        
        # Send response to frontend
        response_msg = f"""✅ Test barcode {barcode} processed successfully!

**API Calls Completed:**
• First call: {api_result_1.get('message', 'Success')}
• Second call: {api_result_2.get('message', 'Success')}

**Next Step:** Click 'Confirm Registration' to complete the process."""
        
        return response_msg
        
    except Exception as e:
        logger.error(f"Error in register_device_id: {str(e)}")
        led_controller.blink_led("red")
        return f"❌ Error: {str(e)}"

def confirm_registration(barcode, device_id):
    """Step 2: Frontend confirms registration, send confirmation message, save device in DB, send to IoT"""
    try:
        # FIRST: Check if device ID is already registered in database
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device['device_id'] == device_id for device in registered_devices)
        
        if device_already_registered:
            logger.info(f"🚫 BLOCKING DUPLICATE REGISTRATION - Device ID {device_id} already exists in database")
            led_controller.blink_led("yellow")  # Use yellow to indicate already registered
            
            # Get registration date for display
            existing_device = next((dev for dev in registered_devices if dev['device_id'] == device_id), None)
            reg_date = existing_device.get('registration_date', 'Unknown') if existing_device else 'Unknown'
            
            return f"""⚠️ Device Already Registered

**Device Details:**
• Device ID: {device_id}
• Registration Date: {reg_date}

**Status:** This device is already registered and ready for barcode scanning operations.
🚫 NO API CALL MADE - Preventing duplicate registration."""
        
        # Check if test barcode has been scanned
        test_scan = local_db.get_test_barcode_scan()
        if not test_scan:
            led_controller.blink_led("red")
            return "❌ No test barcode scanned. Please scan the test barcode (817994ccfe14) first."
        
        is_online = api_client.is_online()
        if not is_online:
            led_controller.blink_led("red")
            return "❌ Device is offline. Cannot confirm registration."
        
        # Use the device_id provided or get from test scan
        if not device_id or not device_id.strip():
            # If no device ID provided, use the test barcode as device ID
            device_id = test_scan['barcode']
        
        # Log the device ID being used for registration
        logger.info(f"✅ PROCEEDING WITH NEW REGISTRATION - Device ID: {device_id}")
        
        # Call confirmRegistration API (ONLY for new devices)
        logger.info(f"📤 SENDING SINGLE REGISTRATION NOTIFICATION for device: {device_id}")
        api_result = api_client.confirm_registration(device_id)
        
        # Check API result
        if not api_result.get("success", False):
            led_controller.blink_led("red")
            return f"❌ Registration failed: {api_result.get('message', 'Unknown error')}"
        
        # Save device to database AFTER successful API call
        registration_data = {
            'device_id': device_id,
            'registration_date': datetime.now(timezone.utc).isoformat(),
            'test_barcode': test_scan['barcode'],
            'registration_method': 'api_confirmation'
        }
        
        local_db.save_device_registration(device_id, registration_data)
        logger.info(f"💾 Device {device_id} saved to local database")
        
        # Send confirmation to IoT Hub
        try:
            config = load_config()
            if config and "iot_hub" in config and "connection_string" in config["iot_hub"]:
                from utils.dynamic_registration_service import get_dynamic_registration_service
                registration_service = get_dynamic_registration_service()
                device_connection_string = registration_service.register_device_with_azure(device_id)
                
                if device_connection_string:
                    hub_client = HubClient(device_connection_string)
                    confirmation_message = {
                        "deviceId": device_id,
                        "messageType": "device_registration",
                        "status": "registered",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": "Device registration confirmed via API"
                    }
                    
                    hub_success = hub_client.send_message(confirmation_message)
                    if hub_success:
                        logger.info(f"✅ Registration confirmation sent to IoT Hub for device {device_id}")
                    else:
                        logger.warning(f"⚠️ Failed to send registration confirmation to IoT Hub for device {device_id}")
                else:
                    logger.warning(f"⚠️ Could not get device connection string for {device_id}")
            else:
                logger.warning("⚠️ IoT Hub configuration not found")
        except Exception as iot_error:
            logger.error(f"❌ IoT Hub registration error: {iot_error}")
        
        # Clear test barcode scan after successful registration
        local_db.clear_test_barcode_scan()
        
        led_controller.blink_led("green")
        
        return f"""🎉 Registration Successful!

**Device Details:**
• Device ID: {device_id}
• Registration Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
• API Status: ✅ Confirmed
• IoT Hub: ✅ Notified
• Database: ✅ Saved

**Status:** Device is now ready for barcode scanning operations!"""
                
        
    except Exception as e:
        logger.error(f"Error in confirm_registration: {str(e)}")
        led_controller.blink_led("red")
        return f"❌ Registration Error: {str(e)}"


# ============================================================================
# BARCODE PROCESSING FUNCTIONS
# ============================================================================

def is_barcode_registered(barcode: str) -> bool:
    """Check if a barcode is registered in the system"""
    try:
        from utils.barcode_device_mapper import BarcodeDeviceMapper
        mapper = BarcodeDeviceMapper()
        
        # Check if barcode exists in the mapping
        device_id = mapper.get_device_id_for_barcode(barcode)
        if not device_id:
            return False
            
        # Check if the mapped device is registered
        from utils.dynamic_device_manager import DynamicDeviceManager
        device_manager = DynamicDeviceManager()

        device_registered = (
            device_manager.is_device_registered(device_id) or 
            any(dev.get('device_id') == device_id for dev in (local_db.get_registered_devices() or []))
        )
        
        if device_registered:
            return True
            
        registered_devices = local_db.get_registered_devices()
        return any(dev.get('device_id') == device_id for dev in registered_devices) if registered_devices else False
        
    except Exception as e:
        logger.error(f"Error checking barcode registration: {e}")
        return False


def process_barcode_scan(barcode, device_id=None):
    """Process a barcode scan and determine if it's a valid product or device ID"""
    try:
        if not barcode or barcode.strip() == "":
            return "❌ Please enter a barcode."
        
        barcode = barcode.strip()
        
        # Check if device is already registered
        current_device_id = local_db.get_device_id()
        
        # If device is registered and we have a barcode, process it normally
        if current_device_id and barcode:
            # Save scan to local database
            timestamp = local_db.save_scan(current_device_id, barcode)
            logger.info(f"Saved scan to local database: {current_device_id}, {barcode}, {timestamp}")
            
            # Send to IoT Hub using dynamic registration service
            try:
                config = load_config()
                if config and "iot_hub" in config and "connection_string" in config["iot_hub"]:
                    from utils.dynamic_registration_service import get_dynamic_registration_service
                    registration_service = get_dynamic_registration_service()
                    device_connection_string = registration_service.register_device_with_azure(current_device_id)
                    
                    if device_connection_string:
                        hub_client = HubClient(device_connection_string)
                        
                        # Create barcode scan message
                        scan_message = {
                            "deviceId": current_device_id,
                            "barcode": barcode,
                            "quantity": 1,
                            "messageType": "barcode_scan",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "message": f"Barcode {barcode} scanned by device {current_device_id}"
                        }
                        
                        success = hub_client.send_message(scan_message, current_device_id)
                        if success:
                            return f"✅ Barcode {barcode} scanned and sent to IoT Hub successfully!"
                        else:
                            return f"⚠️ Barcode {barcode} scanned and saved locally, but failed to send to IoT Hub."
                    else:
                        return f"⚠️ Barcode {barcode} scanned and saved locally, but could not get device connection string."
                else:
                    return f"⚠️ Barcode {barcode} scanned and saved locally, but IoT Hub configuration not found."
            except Exception as e:
                logger.error(f"Error sending to IoT Hub: {e}")
                return f"⚠️ Barcode {barcode} scanned and saved locally, but error sending to IoT Hub: {str(e)}"
        
        # If no device ID is registered yet, check if this barcode is a valid device ID
        if not current_device_id:
            is_online = api_client.is_online()
            if not is_online:
                return "❌ Device appears to be offline. Cannot validate device ID."
            
            # Test if this is a valid device ID using the new API
            result = api_client.validate_and_save_device(barcode)
            
            if result.get('success') and result.get('device_data'):
                device_data = result.get('device_data')
                actual_device_id = device_data.get('deviceId', barcode)
                
                # Save the device ID to local database
                local_db.save_device_id(actual_device_id)
                
                # Send to IoT Hub
                try:
                    config = load_config()
                    if config:
                        device_connection_string = config.get("iot_hub", {}).get("devices", {}).get(actual_device_id, {}).get("connection_string", None)
                        
                        if not device_connection_string:
                            device_connection_string = config.get("iot_hub", {}).get("connection_string", None)
                        
                        if device_connection_string:
                            hub_client = HubClient(device_connection_string)
                            registration_message = {
                                "scannedBarcode": barcode,
                                "deviceId": actual_device_id,
                                "messageType": "registration",
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                            
                            iot_success = hub_client.send_message(barcode, actual_device_id)
                            iot_status = "✅ Sent to IoT Hub" if iot_success else "⚠️ Failed to send to IoT Hub"
                        else:
                            iot_status = "⚠️ No IoT Hub connection string available"
                    else:
                        iot_status = "⚠️ Failed to load configuration"
                except Exception as e:
                    logger.error(f"Error sending to IoT Hub: {str(e)}")
                    iot_status = f"⚠️ Error: {str(e)}"
                
                return f"""🎉 Device Registration Successful!

**Device Details:**
• Device ID: {actual_device_id}
• Customer ID: {device_data.get('customerId', 'N/A')}
• Verified: {device_data.get('verified', False)}
• Registered At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Device ID registered with API
• ✅ Device saved in local database
• {iot_status}

**Status:** Device is now ready for barcode scanning operations!
✅ Device will appear on frontend dashboard at https://iot.caleffionline.it/devices"""
            
            elif result.get('is_test_barcode'):
                # Save test barcode scan
                local_db.save_test_barcode_scan(barcode)
                
                return f"""🧪 This is a test barcode.

Test barcode {barcode} has been saved.
Please proceed with device registration confirmation."""
            
            else:
                return f"❌ Invalid barcode. Please scan a valid device ID or test barcode."
        
        # If we have a device ID and barcode, process the barcode scan
        if device_id and barcode:
            # Validate barcode using the EAN validator
            try:
                validated_barcode = validate_ean(barcode)
            except BarcodeValidationError as e:
                return f"❌ Barcode validation error: {str(e)}"
            
            # Process EAN barcode scan
            return process_ean_barcode_scan(validated_barcode, device_id.strip())
    
    except Exception as e:
        logger.error(f"Error in process_barcode_scan: {str(e)}")
        return f"❌ Error processing barcode: {str(e)}"

# ============================================================================
# DISPLAY AND STATUS FUNCTIONS
# ============================================================================

def get_recent_scans_display():
    """Get recent scanned barcodes for frontend display"""
    try:
        recent_scans = local_db.get_recent_scans(10)  # Get last 10 scans
        
        if not recent_scans:
            return "📋 **RECENT SCANNED BARCODES**\n\n❌ No barcode scans found."
        
        display_text = "📋 **RECENT SCANNED BARCODES**\n\n"
        
        for i, scan in enumerate(recent_scans, 1):
            device_id = scan['device_id']
            barcode = scan['barcode']
            timestamp = scan['timestamp']
            quantity = scan.get('quantity', 1)
            
            display_text += f"**{i}.** `{barcode}`\n"
            display_text += f"   • Device: {device_id}\n"
            display_text += f"   • Time: {timestamp}\n"
            display_text += f"   • Quantity: {quantity}\n\n"
        
        return display_text
        
    except Exception as e:
        logger.error(f"Error getting recent scans: {str(e)}")
        return f"❌ Error getting recent scans: {str(e)}"

def get_registration_status():
    """Get the current device registration status"""
    try:
        # Check if test barcode has been scanned
        test_scan = local_db.get_test_barcode_scan()
        test_barcode_scanned = test_scan is not None
        
        # Check if device ID is saved
        device_id = local_db.get_device_id()
        device_registered = device_id is not None
        
        status_text = "📋 **DEVICE REGISTRATION STATUS**\n\n"
        
        # Test barcode status
        if test_barcode_scanned:
            status_text += f"✅ **Test Barcode:** Scanned ({test_scan['barcode']}) at {test_scan['timestamp']}\n"
        else:
            status_text += "❌ **Test Barcode:** Not scanned - Please scan: 817994ccfe14\n"
        
        # Device registration status
        if device_registered:
            status_text += f"✅ **Device ID:** Registered ({device_id})\n"
        else:
            status_text += "❌ **Device ID:** Not registered - Please confirm registration\n"
        
        # Overall status
        if test_barcode_scanned and device_registered:
            status_text += "\n🎉 **DEVICE READY:** Can send messages to IoT Hub"
        else:
            status_text += "\n⚠️ **DEVICE NOT READY:** Complete registration steps above"
        
        return status_text
        
    except Exception as e:
        logger.error(f"Error getting registration status: {str(e)}")
        return f"❌ Error getting registration status: {str(e)}"

def process_unsent_messages(auto_retry=False):
    """Process any unsent messages in the local database and try to send them to IoT Hub
    OPTIMIZED VERSION: Uses batch processing, connection caching, and reduced database calls
    
    Args:
        auto_retry (bool): If True, runs in background mode without returning status messages
        
    Returns:
        str: Status message if not in auto_retry mode, None otherwise
    """
    # This function is deprecated as the connection manager now handles automatic retry
    # Keeping it for backward compatibility but it just returns a message
    logger.info("process_unsent_messages is deprecated - connection manager handles automatic retry")
    return "✅ Automatic message retry is now handled by the connection manager in the background."

def get_pi_connection_status_display():
    """Get the current Pi connection status display string."""
    try:
        # Check if Pi is connected
        connected = check_raspberry_pi_connection()
        
        if connected:
            # Get Pi IP if available
            pi_ip = get_primary_raspberry_pi_ip()
            if pi_ip:
                return f"✅ External Raspberry Pi connected: {pi_ip}"
            else:
                return "✅ Raspberry Pi connected"
        else:
            return "❌ No external Raspberry Pi devices found on network"
    except Exception as e:
        logger.error(f"Error getting Pi connection status: {e}")
        return "⚠️ Error checking Pi connection status"

def refresh_pi_connection():
    """Refresh Raspberry Pi connection status and return updated display."""
    logger.info("🔄 Refreshing Raspberry Pi connection...")
    
    # Check connection
    connected = check_raspberry_pi_connection()
    
    # Get updated status display
    status_display = get_pi_connection_status_display()
    
    if connected:
        led_controller.blink_led("green")
        logger.info("✅ Connection refresh successful")
    else:
        led_controller.blink_led("red")
        logger.warning("❌ Connection refresh failed")
    
    return status_display

# ============================================================================
# DEVICE INFORMATION FUNCTIONS
# ============================================================================

def get_device_mac_address():
    """
    Get the current device's MAC address dynamically.
    Works on both Raspberry Pi and other Linux systems including live servers.
    
    Returns:
        str: MAC address if found, None otherwise
    """
    import re
    
    # Method 1: Use ip link command (most reliable for servers)
    try:
        result = subprocess.run(
            ["ip", "link", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Look for MAC addresses in the output
            mac_pattern = r'link/ether ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
            matches = re.findall(mac_pattern, result.stdout.lower())
            for mac in matches:
                if mac != "00:00:00:00:00:00":
                    logger.info(f"📍 Device MAC address detected via ip link: {mac}")
                    return mac
    except Exception as e:
        logger.warning(f"ip link method failed: {e}")
    
    # Method 2: Use ifconfig command (fallback)
    try:
        result = subprocess.run(
            ["ifconfig"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Look for MAC addresses in ifconfig output
            mac_pattern = r'ether ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
            matches = re.findall(mac_pattern, result.stdout.lower())
            for mac in matches:
                if mac != "00:00:00:00:00:00":
                    logger.info(f"📍 Device MAC address detected via ifconfig: {mac}")
                    return mac
    except Exception as e:
        logger.warning(f"ifconfig method failed: {e}")
    
    # Method 3: Check /sys/class/net files (if available)
    try:
        interfaces = ['eth0', 'wlan0', 'enp0s3', 'ens33', 'eno1', 'ens160']
        for interface in interfaces:
            try:
                with open(f"/sys/class/net/{interface}/address", 'r') as f:
                    mac = f.read().strip().lower()
                    if mac and mac != "00:00:00:00:00:00" and ":" in mac:
                        logger.info(f"📍 Device MAC address detected from {interface}: {mac}")
                        return mac
            except (FileNotFoundError, PermissionError):
                continue
    except Exception as e:
        logger.debug(f"/sys/class/net method failed: {e}")
    
    # Method 4: Use hostname -I + ARP lookup (server-friendly)
    try:
        # Get local IP first
        ip_result = subprocess.run(
            ["hostname", "-I"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if ip_result.returncode == 0 and ip_result.stdout.strip():
            local_ip = ip_result.stdout.strip().split()[0]
            
            # Try to find MAC via ARP for local IP
            arp_result = subprocess.run(
                ["arp", "-n", local_ip],
                capture_output=True,
                text=True,
                timeout=3
            )
            if arp_result.returncode == 0:
                # Parse ARP output for MAC
                mac_match = re.search(r'([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', arp_result.stdout.lower())
                if mac_match:
                    mac = mac_match.group(1)
                    if mac != "00:00:00:00:00:00":
                        logger.info(f"📍 Device MAC address detected via ARP lookup: {mac}")
                        return mac
    except Exception as e:
        logger.debug(f"ARP lookup method failed: {e}")
    
    logger.error("❌ Could not detect device MAC address using any method")
    return None

def get_device_ip():
    """
    Get the current device's IP address using multiple methods.
    Works on both Raspberry Pi and other Linux systems.
    
    Returns:
        str: IP address if found, None otherwise
    """
    try:
        # Method 1: Use hostname -I (most reliable for Pi)
        result = subprocess.run(
            ["hostname", "-I"], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Get first IPv4 address (ignore IPv6)
            ips = result.stdout.strip().split()
            for ip in ips:
                if '.' in ip and not ip.startswith('127.'):  # IPv4 and not localhost
                    logger.info(f"📍 Device IP detected via hostname -I: {ip}")
                    return ip
    except Exception as e:
        logger.warning(f"hostname -I method failed: {e}")
    
    try:
        # Method 2: Check multiple network interfaces
        interfaces = ['eth0', 'wlan0', 'enp0s3', 'ens33']
        for interface in interfaces:
            result = subprocess.run(
                f"ip addr show {interface} | grep 'inet ' | awk '{{print $2}}' | cut -d/ -f1",
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip()
                if ip and not ip.startswith('127.'):
                    logger.info(f"📍 Device IP detected via {interface}: {ip}")
                    return ip
    except Exception as e:
        logger.warning(f"Interface scanning method failed: {e}")
    
    try:
        # Method 3: Use ip route (fallback)
        result = subprocess.run(
            "/sbin/ip route get 8.8.8.8 | awk '{print $7}' | head -1",
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            ip = result.stdout.strip()
            if ip and not ip.startswith('127.'):
                logger.info(f"📍 Device IP detected via route: {ip}")
                return ip
    except Exception as e:
        logger.warning(f"Route method failed: {e}")
    
    logger.error("❌ Could not detect device IP address")
    return None


def check_local_pi_and_notify_server():
    """
    Check if Raspberry Pi is locally attached and send MAC address notification to live server.
    Uses dynamic MAC address detection instead of static IP addresses.
    
    Returns:
        dict: Status information including pi_attached (True/False) and notification result
    """
    try:
        logger.info("🔍 Checking Pi device status and sending MAC address to live server...")
        
        # Get current device MAC address dynamically
        device_mac = get_device_mac_address()
        pi_attached = device_mac is not None
        
        # Generate unique device ID
        device_id = generate_dynamic_device_id()
        
        # Create JSON payload with MAC address for live server
        pi_details = {
            'mac_address': device_mac,
            'device_id': device_id,
            'timestamp': datetime.now().isoformat(),
            'detection_method': 'dynamic_mac_detection' if device_mac else 'failed',
            'device_type': 'raspberry_pi' if device_mac else 'unknown'
        }
        
        if pi_attached:
            logger.info(f"📍 Pi Status: ✅ Device Connected with MAC: {device_mac}")
        else:
            logger.info("📍 Pi Status: ❌ Device Not Connected - No MAC address detected")
        
        # Send to IoT Hub with MAC address
        iot_result = _send_pi_status_to_iot_hub(device_id, pi_attached, pi_details)
        
        # Send MAC address to live server in JSON format
        api_result = _send_pi_status_notification({
            'pi_attached': pi_attached,
            'device_id': device_id,
            'mac_address': device_mac,
            'timestamp': datetime.now().isoformat(),
            'pi_details': pi_details,
            'check_type': 'mac_address_detection'
        })
        
        # Prepare response with MAC address
        response = {
            'pi_attached': pi_attached,
            'pi_mac_address': device_mac,
            'device_id': device_id,
            'iot_hub_sent': iot_result['success'],
            'api_notification_sent': api_result['success'],
            'iot_hub_details': iot_result,
            'api_details': api_result,
            'timestamp': datetime.now().isoformat()
        }
        
        status_emoji = "✅" if pi_attached else "❌"
        iot_emoji = "📤" if iot_result['success'] else "⚠️"
        api_emoji = "📤" if api_result['success'] else "⚠️"
        
        logger.info(f"{status_emoji} Pi Status Check Complete: {pi_attached}")
        logger.info(f"{iot_emoji} IoT Hub Notification: {'Sent' if iot_result['success'] else 'Failed'}")
        logger.info(f"{api_emoji} API Notification: {'Sent' if api_result['success'] else 'Failed'}")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Error checking Pi status: {e}")
        return {
            'pi_attached': False,
            'pi_ip': None,
            'device_id': None,
            'iot_hub_sent': False,
            'api_notification_sent': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def _send_pi_status_to_iot_hub(device_id, pi_attached, pi_details):
    """
    Send Pi status to IoT Hub using existing hub client.
    
    Args:
        device_id (str): Device identifier
        pi_attached (bool): Whether Pi is attached
        pi_details (dict): Pi connection details
        
    Returns:
        dict: Result of IoT Hub send attempt
    """
    try:
        # Create message payload for IoT Hub
        message_data = {
            "messageType": "device_status",
            "deviceId": device_id,
            "status": "connected" if pi_attached else "disconnected",
            "ip_address": pi_details.get('ip'),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detection_method": pi_details.get('detection_method'),
            "device_info": {
                "pi_attached": pi_attached,
                "connection_details": pi_details
            }
        }
        
        # Get dynamic registration service for device connection
        registration_service = get_dynamic_registration_service()
        device_connection_string = registration_service.register_device_with_azure(device_id)
        
        if not device_connection_string:
            logger.error(f"❌ Failed to get device connection string for {device_id}")
            return {
                'success': False,
                'error': 'Failed to get device connection string'
            }
        
        # Use connection manager to send registration message with Pi checks
        from utils.connection_manager import ConnectionManager
        connection_manager =  ConnectionManager()
        
        # Check Pi availability before sending registration confirmation
        if not connection_manager.check_raspberry_pi_availability():
            logger.warning(f"Registration confirmation blocked: Raspberry Pi not connected for device {device_id}")
            # Save registration message locally for retry
            local_db.save_unsent_message(device_id, json.dumps(message_data), datetime.now())
            return "⚠️ **Registration saved locally - Pi offline**\n\nDevice registration will be confirmed when Raspberry Pi comes online."
        
        # Send registration confirmation via connection manager
        success, status_msg = connection_manager.send_message_with_retry(
            device_id=device_id,
            barcode=json.dumps(message_data),
            quantity=1,
            message_type="device_registration"
        )
        
        if success:
            logger.info(f"✅ Registration confirmation sent to IoT Hub for device {device_id}")
            return {
                'success': True,
                'device_id': device_id,
                'message_type': 'device_status'
            }
        else:
            logger.error(f"❌ Failed to send Pi status to IoT Hub for device {device_id}")
            return {
                'success': False,
                'error': 'IoT Hub send failed'
            }
            
    except Exception as e:
        logger.error(f"❌ Error sending Pi status to IoT Hub: {e}")
        return {
            'success': False,
            'error': str(e)
        }
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Error checking Pi attachment status: {e}")
        return {
            'pi_attached': False,
            'pi_ip': None,
            'notification_sent': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def _send_pi_status_notification(payload):
    """
    Send Pi status notification to server.
    
    Args:
        payload (dict): Notification payload with Pi status
        
    Returns:
        dict: Result of notification attempt
    """
    try:
        # Load configuration to get server notification URL
        config = load_config()
        
        # Try multiple notification endpoints
        notification_urls = [
            config.get("frontend", {}).get("notification_url", "https://iot.caleffionline.it/api/pi-status-notification"),
            "https://api2.caleffionline.it/api/v1/raspberry/piStatus",
            config.get("frontend", {}).get("base_url", "https://iot.caleffionline.it") + "/api/pi-status"
        ]
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'RaspberryPi-BarcodeScanner/1.0'
        }
        
        last_error = None
        
        for url in notification_urls:
            try:
                logger.info(f"📤 Sending Pi status notification to: {url}")
                
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code in [200, 201, 202]:
                    logger.info(f"✅ Pi status notification sent successfully to {url}")
                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'url': url,
                        'response': response.text[:200] if response.text else None
                    }
                else:
                    logger.warning(f"⚠️ Server returned status {response.status_code} for {url}")
                    last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ Failed to send notification to {url}: {e}")
                last_error = str(e)
                continue
        
        # If all URLs failed
        logger.error(f"❌ Failed to send Pi status notification to all endpoints. Last error: {last_error}")
        return {
            'success': False,
            'error': last_error,
            'attempted_urls': notification_urls
        }
        
    except Exception as e:
        logger.error(f"❌ Error sending Pi status notification: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Create Gradio interface
with gr.Blocks(title="Barcode Scanner") as app:
    gr.Markdown("# Barcode Scanner")
    
    with gr.Row():
        # Left column for barcode scanning
        with gr.Column():
            gr.Markdown("## Scan Barcode")
            
            barcode_input = gr.Textbox(label="Barcode", placeholder="Scan or enter barcode")
            device_id_input = gr.Textbox(label="Device ID", placeholder="Enter device ID (optional)")
            
            with gr.Row():
                send_button = gr.Button("Send Barcode", variant="primary")
                clear_button = gr.Button("Clear")
                
            output_text = gr.Markdown("")
            
        with gr.Column():
            gr.Markdown("## Device Registration & Status")
            
            # Real-time Pi Connection Status (updated automatically)
            pi_status_display = gr.Markdown("## 📡 Raspberry Pi Connection Status\n\n*Loading status...*")
            
            gr.Markdown("### Two-Step Registration Process")
            with gr.Row():
                scan_test_barcode_button = gr.Button("1. Scan Any Test Barcode (Dynamic)", variant="primary")
                confirm_registration_button = gr.Button("2. Confirm Registration", variant="primary")
                
            with gr.Row():
                process_unsent_button = gr.Button("Process Unsent Messages")
                pi_status_button = gr.Button("Refresh Pi Status", variant="secondary")
                
            status_text = gr.Markdown("")
            
            
    # Event handlers
    send_button.click(
        fn=process_barcode_scan,
        inputs=[barcode_input, device_id_input],
        outputs=[output_text]
    )
    
    clear_button.click(
        fn=lambda: ("", ""),
        inputs=[],
        outputs=[barcode_input, device_id_input]
    )
    
    # Two-step registration handlers
    scan_test_barcode_button.click(
        fn=lambda: register_device_id("817994ccfe14"),
        inputs=[],
        outputs=[status_text]
    )
    
    confirm_registration_button.click(
        fn=confirm_registration,
        inputs=[barcode_input, device_id_input],
        outputs=[status_text]
    )
    

    
    process_unsent_button.click(
        fn=process_unsent_messages_ui,
        inputs=[],
        outputs=[status_text],
        show_progress='full'
    )
    
    pi_status_button.click(
        fn=refresh_pi_connection,
        inputs=[],
        outputs=[pi_status_display]
    )
    

logger.info("🚀 Initializing Raspberry Pi Barcode Scanner System...")

# Check if running on Raspberry Pi and initialize accordingly
if IS_RASPBERRY_PI:
    logger.info("🔍 Detected: Running on Raspberry Pi device")
    logger.info("📱 Mode: Direct Pi device with Azure IoT Hub connection")
    
    # Initialize Pi device service for direct IoT Hub connection
    pi_device_service = RaspberryPiDeviceService()
    
    # Start barcode scanning service
    pi_device_service.start_barcode_scanning_service()
    
    logger.info("✅ Raspberry Pi Device Service initialized")
    logger.info("📡 Connected to Azure IoT Hub for inventory tracking")
    logger.info("📱 Ready to scan barcodes - data will be published to IoT Hub")
    
else:
    logger.info("🔍 Detected: Running on server/desktop (will search for external Pi devices)")
    logger.info("📱 Mode: Network-based Pi discovery and management")
    
    # Simplified Pi connection check - no excessive logging
    pi_connected = check_raspberry_pi_connection()
    
    if pi_connected:
        logger.info("✅ Raspberry Pi connection established")
    else:
        logger.info("ℹ️ No Raspberry Pi found - system will auto-detect when Pi connects")
    
    logger.info("📡 IoT Hub connection established")
    logger.info("🎯 System ready for plug-and-play barcode scanning")
    logger.info("🌐 Web interface will be available at: http://localhost:7860")

logger.info("🚀 Barcode scanner system initialized")
logger.info("📱 System configured for Azure IoT Hub inventory tracking")

# System initialization complete
logger.info("✅ System initialization complete")

# ==========================================
# PI HEARTBEAT SYSTEM FOR PLUG-AND-PLAY
# ==========================================

class PiHeartbeatService:
    """
    Pi Heartbeat Service for cloud environments where LAN discovery fails.
    Ensures server can always detect Pi devices regardless of network topology.
    """
    
    def __init__(self, config):
        self.config = config
        self.device_id = None
        self.server_url = None
        self.heartbeat_interval = 30  # seconds
        self.registration_interval = 300  # 5 minutes
        self.running = False
        self.heartbeat_thread = None
        self.registration_thread = None
        self.last_heartbeat = None
        self.last_registration = None
        self.connection_string = None
        
        # Get device info
        self.device_info = self._get_device_info()
        logger.info(f"🔄 Pi Heartbeat Service initialized for device: {self.device_info.get('device_id', 'unknown')}")
    
    def _get_device_info(self):
        """Get comprehensive device information for heartbeat"""
        try:
            # Generate consistent device ID based on hardware
            mac = get_local_device_mac()
            if mac:
                device_id = f"pi-{mac.replace(':', '').lower()[-8:]}"
            else:
                device_id = f"pi-{uuid.uuid4().hex[:8]}"
            
            # Get network info
            hostname = socket.gethostname()
            
            # Get local IP addresses
            local_ips = []
            try:
                # Get all network interfaces
                result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    local_ips = result.stdout.strip().split()
            except Exception as e:
                logger.warning(f"Could not get local IPs: {e}")
            
            # Get system info
            system_info = {
                'platform': os.uname().sysname,
                'architecture': os.uname().machine,
                'hostname': hostname,
                'python_version': sys.version.split()[0]
            }
            
            return {
                'device_id': device_id,
                'mac_address': mac,
                'hostname': hostname,
                'local_ips': local_ips,
                'system_info': system_info,
                'services': {
                    'barcode_scanner': True,
                    'ssh': self._check_service_port(22),
                    'web': self._check_service_port(5000)
                }
            }
        except Exception as e:
            logger.error(f"❌ Failed to get device info: {e}")
            return {'device_id': f"pi-{uuid.uuid4().hex[:8]}"}
    
    def _check_service_port(self, port):
        """Check if a service port is available"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _discover_server(self):
        """Discover the barcode scanner server"""
        try:
            # Try configured server URLs first
            server_candidates = [
                "https://iot.caleffionline.it",
                "https://api2.caleffionline.it",
                "http://localhost:7860",
                "http://127.0.0.1:7860"
            ]
            
            # Add any configured server URLs
            if self.config:
                frontend_config = self.config.get("frontend", {})
                if frontend_config.get("base_url"):
                    server_candidates.insert(0, frontend_config["base_url"])
            
            for server_url in server_candidates:
                try:
                    # Test server connectivity
                    response = requests.get(f"{server_url}/api/health", timeout=10)
                    if response.status_code == 200:
                        health_data = response.json()
                        if "barcode" in health_data.get("service", "").lower():
                            logger.info(f"✅ Server discovered: {server_url}")
                            return server_url
                except Exception as e:
                    logger.debug(f"Server {server_url} not reachable: {e}")
                    continue
            
            logger.warning("⚠️ No barcode scanner server found")
            return None
            
        except Exception as e:
            logger.error(f"❌ Server discovery failed: {e}")
            return None
    
    def _register_with_server(self):
        """Register Pi device with the server"""
        try:
            if not self.server_url:
                self.server_url = self._discover_server()
                if not self.server_url:
                    return False
            
            registration_data = {
                "device_id": self.device_info["device_id"],
                "device_type": "raspberry_pi",
                "mac_address": self.device_info.get("mac_address"),
                "hostname": self.device_info.get("hostname"),
                "local_ips": self.device_info.get("local_ips", []),
                "system_info": self.device_info.get("system_info", {}),
                "services": self.device_info.get("services", {}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "heartbeat_interval": self.heartbeat_interval,
                "capabilities": ["barcode_scanning", "iot_hub_messaging", "local_storage"]
            }
            
            # Register device
            response = requests.post(
                f"{self.server_url}/api/v1/raspberry/register",
                json=registration_data,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                self.connection_string = result.get("connection_string")
                self.device_id = self.device_info["device_id"]
                
                logger.info(f"✅ Pi device registered successfully: {self.device_id}")
                
                # Save registration info to config
                self._save_registration_info(result)
                
                return True
            else:
                logger.warning(f"⚠️ Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Registration error: {e}")
            return False
    
    def _save_registration_info(self, registration_result):
        """Save registration information to config"""
        try:
            config = load_config()
            if not config:
                config = {}
            
            config["pi_heartbeat"] = {
                "device_id": self.device_id,
                "server_url": self.server_url,
                "connection_string": self.connection_string,
                "last_registration": datetime.now(timezone.utc).isoformat(),
                "registration_result": registration_result
            }
            
            save_config(config)
            logger.info("💾 Pi heartbeat registration saved to config")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not save registration info: {e}")
    
    def _send_heartbeat(self):
        """Send heartbeat to server"""
        try:
            if not self.server_url or not self.device_id:
                return False
            
            # Get current status
            current_status = {
                "device_id": self.device_id,
                "status": "online",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "local_ips": self.device_info.get("local_ips", []),
                "services": {
                    "barcode_scanner": True,
                    "ssh": self._check_service_port(22),
                    "web": self._check_service_port(5000)
                },
                "system_metrics": {
                    "uptime": time.time(),
                    "memory_available": True,  # Simplified for now
                    "disk_space": True
                }
            }
            
            # Send heartbeat
            response = requests.post(
                f"{self.server_url}/api/v1/raspberry/heartbeat",
                json=current_status,
                timeout=15,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                self.last_heartbeat = datetime.now(timezone.utc)
                logger.debug(f"💓 Heartbeat sent successfully")
                return True
            else:
                logger.warning(f"⚠️ Heartbeat failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat error: {e}")
            return False
    
    def _heartbeat_worker(self):
        """Background worker for sending heartbeats"""
        logger.info("💓 Pi heartbeat worker started")
        
        while self.running:
            try:
                # Send heartbeat
                success = self._send_heartbeat()
                
                if not success:
                    # If heartbeat fails, try to re-register
                    logger.info("🔄 Heartbeat failed, attempting re-registration...")
                    self._register_with_server()
                
                # Wait for next heartbeat
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"❌ Heartbeat worker error: {e}")
                time.sleep(self.heartbeat_interval)
    
    def _registration_worker(self):
        """Background worker for periodic re-registration"""
        logger.info("📝 Pi registration worker started")
        
        while self.running:
            try:
                # Wait for registration interval
                time.sleep(self.registration_interval)
                
                # Re-register to ensure server has latest info
                if self.running:
                    logger.info("🔄 Periodic re-registration...")
                    self._register_with_server()
                    
            except Exception as e:
                logger.error(f"❌ Registration worker error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def start(self):
        """Start the Pi heartbeat service"""
        try:
            if self.running:
                logger.warning("⚠️ Pi heartbeat service already running")
                return
            
            logger.info("🚀 Starting Pi heartbeat service...")
            
            # Initial registration
            registration_success = self._register_with_server()
            if not registration_success:
                logger.warning("⚠️ Initial registration failed, will retry in background")
            
            # Start background workers
            self.running = True
            
            # Start heartbeat thread
            self.heartbeat_thread = threading.Thread(
                target=self._heartbeat_worker,
                name="PiHeartbeatWorker",
                daemon=True
            )
            self.heartbeat_thread.start()
            
            # Start registration thread
            self.registration_thread = threading.Thread(
                target=self._registration_worker,
                name="PiRegistrationWorker", 
                daemon=True
            )
            self.registration_thread.start()
            
            logger.info("✅ Pi heartbeat service started successfully")
            logger.info(f"💓 Heartbeat interval: {self.heartbeat_interval}s")
            logger.info(f"📝 Registration interval: {self.registration_interval}s")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Pi heartbeat service: {e}")
            self.running = False
    
    def stop(self):
        """Stop the Pi heartbeat service"""
        try:
            logger.info("🛑 Stopping Pi heartbeat service...")
            self.running = False
            
            # Send final offline status
            if self.server_url and self.device_id:
                try:
                    offline_status = {
                        "device_id": self.device_id,
                        "status": "offline",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    requests.post(
                        f"{self.server_url}/api/v1/raspberry/heartbeat",
                        json=offline_status,
                        timeout=10
                    )
                    logger.info("📤 Offline status sent")
                except Exception as e:
                    logger.warning(f"⚠️ Could not send offline status: {e}")
            
            # Wait for threads to finish
            if self.heartbeat_thread and self.heartbeat_thread.is_alive():
                self.heartbeat_thread.join(timeout=5)
            
            if self.registration_thread and self.registration_thread.is_alive():
                self.registration_thread.join(timeout=5)
            
            logger.info("✅ Pi heartbeat service stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping Pi heartbeat service: {e}")

# Initialize Pi Heartbeat Service
pi_heartbeat_service = None
try:
    config = load_config()
    pi_heartbeat_service = PiHeartbeatService(config)
    pi_heartbeat_service.start()
    logger.info("🔄 Pi heartbeat system enabled for plug-and-play discovery")
except Exception as e:
    logger.error(f"❌ Failed to initialize Pi heartbeat service: {e}")

# Initialize Pi connectivity monitoring
config = load_config()
raspberry_pi_config = config.get("raspberry_pi", {})

# Start dynamic discovery for local network scanning
if raspberry_pi_config.get("dynamic_discovery", False):
    try:
        from utils.dynamic_pi_discovery import DynamicPiDiscovery
        global dynamic_pi_discovery
        dynamic_pi_discovery = DynamicPiDiscovery(config)
        dynamic_pi_discovery.start_discovery()
        logger.info("🔍 Dynamic Pi discovery system started")
    except Exception as e:
        logger.error(f"Failed to start dynamic Pi discovery: {e}")

# Start remote connectivity monitoring for cross-network detection
if raspberry_pi_config.get("remote_connectivity_monitoring", False):
    try:
        from utils.remote_pi_connectivity import RemotePiConnectivity
        global remote_pi_connectivity
        remote_pi_connectivity = RemotePiConnectivity(config)
        remote_pi_connectivity.start_monitoring()
        logger.info("🌐 Remote Pi connectivity monitoring started")
    except Exception as e:
        logger.error(f"Failed to start remote Pi connectivity monitoring: {e}")

# Global variable for Gradio app instance


def update_pi_status_display():
    """Update the Pi status display in the Gradio interface"""
    global gradio_app_instance
    if gradio_app_instance is not None:
        try:
            # Get real-time status
            status_text = refresh_pi_connection()
            # Update the pi_status_display component
            # Note: This is a simplified approach - in a real implementation,
            # you would use Gradio's state management or callbacks
            logger.debug("🔄 Updating Pi status display")
        except Exception as e:
            logger.error(f"Error updating Pi status display: {e}")

def start_periodic_status_updates():
    """Single status update (no background thread)"""
    try:
        update_pi_status_display()
        logger.info("📊 Single status update completed")
    except Exception as e:
        logger.error(f"Status update error: {e}")

def discover_server():
    """Auto-discover server for plug-and-play mode"""
    server_candidates = [
        "https://iot.caleffionline.it",
        "http://iot.caleffionline.it", 
        "http://10.0.0.4:5000",
        "http://192.168.1.1:5000",
        "http://192.168.0.1:5000",
        "http://10.0.0.1:5000"
    ]
    
    for server_url in server_candidates:
        try:
            logger.info(f"🌐 Trying server: {server_url}")
            response = requests.get(f"{server_url}/api/health", timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                if health_data.get("service") == "barcode_scanner_server":
                    logger.info(f"✅ Server discovered: {server_url}")
                    return server_url
                    
        except Exception as e:
            logger.debug(f"❌ Server {server_url} not reachable: {e}")
            continue
    
    logger.error("❌ No server found! Check network connectivity.")
    return None

def register_with_barcode(server_url, registration_barcode):
    """Register Pi device using scanned barcode"""
    try:
        # Generate device ID from barcode + hardware
        mac = get_local_mac_address() or "unknown"
        device_id = f"pi-{registration_barcode[-4:]}-{mac.replace(':', '')[-8:]}"
        
        logger.info(f"📝 Registering device: {device_id} with barcode: {registration_barcode}")
        
        # Registration payload
        registration_data = {
            "device_id": device_id,
            "registration_barcode": registration_barcode,
            "device_type": "raspberry_pi_plug_play",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_info": {
                "hostname": socket.gethostname(),
                "mac_address": mac,
                "registration_method": "barcode_scan_plug_play"
            },
            "plug_and_play": True,
            "client_version": "2.0.0"
        }
        
        # Register with server
        response = requests.post(
            f"{server_url}/api/register_device",
            json=registration_data,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            connection_string = result.get("connection_string")
            
            logger.info("✅ Device registered successfully")
            logger.info(f"🔗 IoT Hub connection received")
            
            # Save config
            config = load_config()
            if not config:
                config = {}
            
            # Update config with device registration info
            config["device_registration"] = {
                "device_id": device_id,
                "server_url": server_url,
                "connection_string": connection_string,
                "registration_time": datetime.now().isoformat()
            }
            
            save_config(config)
            
            return device_id, connection_string
        else:
            logger.error(f"❌ Registration failed: {response.status_code}")
            return None, None
            
    except Exception as e:
        logger.error(f"❌ Registration error: {e}")
        return None, None

def plug_and_play_mode():
    """Plug-and-play registration mode - single attempt"""
    logger.info("📱 PLUG-AND-PLAY MODE ACTIVE")
    logger.info("🔌 Connect your USB barcode scanner")
    logger.info("📊 Scan ANY barcode to register this device")
    
    # Discover server
    server_url = discover_server()
    if not server_url:
        logger.error("❌ Cannot continue without server connection")
        return False
    
    # Single barcode registration attempt
    logger.info("⏳ Ready for barcode scan...")
    
    try:
        print("\n🎯 Scan barcode to register (or type barcode + Enter):")
        barcode = input().strip()
        
        if barcode and len(barcode) >= 6:
            logger.info(f"📊 Barcode scanned: {barcode}")
            
            device_id, connection_string = register_with_barcode(server_url, barcode)
            
            if device_id and connection_string:
                logger.info("✅ REGISTRATION SUCCESSFUL!")
                logger.info(f"🆔 Device ID: {device_id}")
                logger.info("🎉 Device is now ready for barcode scanning")
                return True
            else:
                logger.error("❌ Registration failed")
                return False
        else:
            logger.warning("⚠️ Invalid barcode, please provide a valid barcode")
            return False
            
    except KeyboardInterrupt:
        logger.info("🛑 Registration cancelled")
        return False
    except Exception as e:
        logger.error(f"❌ Registration error: {e}")
        return False

def load_pi_config():
    """Load Pi configuration from main config.json"""
    try:
        config = load_config()
        if config and "device_registration" in config:
            return config["device_registration"]
    except Exception as e:
        logger.warning(f"⚠️ Could not load Pi config: {e}")
    return None

def check_for_updates(server_url, device_id, current_version="2.0.0"):
    """Check for OTA updates from server"""
    try:
        logger.info("🔍 Checking for updates...")
        
        response = requests.get(
            f"{server_url}/api/ota/check_update",
            params={
                "device_id": device_id,
                "current_version": current_version
            },
            timeout=10
        )
        
        if response.status_code == 200:
            update_info = response.json()
            
            if update_info.get("has_update", False):
                logger.info(f"📦 Update available: {update_info.get('latest_version')}")
                return update_info
            else:
                logger.info("✅ No updates available")
                return None
        else:
            logger.warning(f"⚠️ Update check failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Update check error: {e}")
        return None

def download_and_apply_update(server_url, update_info):
    """Download and apply OTA update"""
    try:
        logger.info(f"📥 Downloading update {update_info.get('latest_version')}...")
        
        # Download update package
        download_url = f"{server_url}/api/ota/download_update"
        response = requests.get(
            download_url,
            params={"update_id": update_info.get("update_id")},
            stream=True,
            timeout=300
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Download failed: {response.status_code}")
            return False
        
        # Save update file
        update_file = f"/tmp/barcode_scanner_update_{update_info.get('update_id')}.zip"
        with open(update_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Create backup
        backup_file = f"/tmp/barcode_scanner_backup_{int(time.time())}.tar.gz"
        backup_cmd = f"tar -czf {backup_file} -C /opt/barcode-scanner ."
        subprocess.run(backup_cmd, shell=True, check=True)
        logger.info(f"💾 Backup created: {backup_file}")
        
        # Extract and apply update
        import zipfile
        import tempfile
        
        extract_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(update_file, 'r') as zipf:
            zipf.extractall(extract_dir)
        
        # Copy updated files
        import shutil
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, extract_dir)
                dest_file = os.path.join("/opt/barcode-scanner", rel_path)
                
                # Create directory if needed
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                shutil.copy2(src_file, dest_file)
        
        # Clean up
        os.remove(update_file)
        shutil.rmtree(extract_dir)
        
        logger.info("✅ Update applied successfully")
        
        # Notify server of successful update
        try:
            requests.post(
                f"{server_url}/api/ota/update_status",
                json={
                    "device_id": update_info.get("device_id"),
                    "version": update_info.get("latest_version"),
                    "status": "success",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                timeout=10
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not notify update status: {e}")
        
        # Restart service
        logger.info("🔄 Restarting service to apply update...")
        subprocess.run(["sudo", "systemctl", "restart", "barcode-scanner-plug-play"], check=False)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Update application error: {e}")
        return False

def send_single_heartbeat(pi_config):
    """Send single heartbeat to server (no background loop)"""
    try:
        server_url = pi_config.get("server_url")
        device_id = pi_config.get("device_id")
        
        if server_url and device_id:
            heartbeat_data = {
                "device_id": device_id,
                "status": "online",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "system_info": {
                    "hostname": socket.gethostname(),
                    "uptime": time.time()
                }
            }
            
            response = requests.post(
                f"{server_url}/api/device_heartbeat",
                json=heartbeat_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("💓 Heartbeat sent successfully")
                return True
            else:
                logger.warning(f"⚠️ Heartbeat failed: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Heartbeat error: {e}")
        return False

def check_single_update(pi_config):
    """Check for updates once (no background loop)"""
    try:
        server_url = pi_config.get("server_url")
        device_id = pi_config.get("device_id")
        
        if server_url and device_id:
            update_info = check_for_updates(server_url, device_id)
            if update_info:
                logger.info("🔄 Update available - applying...")
                return download_and_apply_update(server_url, update_info)
            else:
                logger.info("✅ No updates available")
                return True
                
    except Exception as e:
        logger.error(f"❌ Update check error: {e}")
        return False

def start_plug_and_play_barcode_service():
    """Start fully automated barcode scanning service without UI"""
    logger.info("🎯 Starting Plug-and-Play Barcode Service...")
    logger.info("📱 Connect your USB barcode scanner and start scanning!")
    logger.info("🔄 System will automatically process all scanned barcodes")
    logger.info("📡 All scans sent to both Frontend API and IoT Hub")
    logger.info("⏹️  Press Ctrl+C to stop the service")
    
    try:
        while True:
            try:
         
                print("\n🎯 Ready for barcode scan (or type barcode + Enter):")
                barcode = input().strip()
                
                if barcode and len(barcode) >= 6:
                    logger.info(f"📊 Barcode scanned: {barcode}")
                    

                    result = process_barcode_scan_auto(barcode)
                    
                    if "✅" in result:
                        logger.info("✅ Barcode processed successfully")
                        print("✅ SUCCESS: Barcode sent to inventory system")
                    else:
                        logger.warning("⚠️ Barcode processing had issues")
                        print("⚠️ WARNING: Check logs for details")
                        
                else:
                    logger.warning("⚠️ Invalid barcode - please scan a valid barcode")
                    print("⚠️ Invalid barcode - try again")
                    
            except EOFError:
            
                logger.info("📱 Waiting for barcode scanner input...")
                time.sleep(1)
                continue
                
    except KeyboardInterrupt:
        logger.info("🛑 Plug-and-Play service stopped by user")
        print("\n🛑 Service stopped. Thank you for using the barcode scanner!")

# Global connection manager instance for stability
_global_connection_manager = None

def get_stable_connection_manager():
    """Get or create a stable connection manager instance"""
    global _global_connection_manager
    if _global_connection_manager is None:
        _global_connection_manager = ConnectionManager()
    return _global_connection_manager

def process_barcode_scan_auto(barcode):
    """Process barcode scan automatically with stable connection"""
    try:
        # Get device ID
        device_id = local_db.get_device_id()
        if not device_id:
            mac_address = get_local_mac_address()
            if mac_address:
                device_id = f"pi-{mac_address.replace(':', '')[-8:]}"
                local_db.save_device_id(device_id)
            else:
                return "❌ No device ID available - registration failed"
        
        # Validate barcode
        try:
            validated_barcode = validate_ean(barcode)
        except BarcodeValidationError:
            validated_barcode = barcode
        
        # Use stable connection manager
        connection_manager = get_stable_connection_manager()
        
        # Simple connectivity check without excessive reconnections
        try:
            logger.info(f"📊 Processing barcode: {validated_barcode}")
            logger.info(f"🆔 Device ID: {device_id}")
            logger.info("📡 Sending single quantity (+1) to IoT Hub...")
            
            # Send ONLY to IoT Hub with single attempt
            success, message = connection_manager.send_message_with_retry(
                device_id=device_id,
                barcode=validated_barcode,
                quantity=1,
                message_type="barcode_scan"
            )
            
            if success:
                logger.info("✅ Quantity +1 sent to IoT Hub successfully")
                return f"✅ Barcode {validated_barcode} - Quantity +1 sent to IoT Hub"
            else:
                logger.warning(f"⚠️ IoT Hub send failed: {message}")
                # Save locally for retry instead of failing
                connection_manager.save_unsent_message(
                    device_id, 
                    json.dumps({
                        "barcode": validated_barcode,
                        "quantity": 1,
                        "timestamp": datetime.now().isoformat()
                    }),
                    datetime.now()
                )
                return f"⚠️ Saved locally for retry - {message}"
                
        except Exception as e:
            logger.error(f"❌ IoT Hub send error: {e}")
            # Save locally for retry
            try:
                connection_manager.save_unsent_message(
                    device_id, 
                    json.dumps({
                        "barcode": validated_barcode,
                        "quantity": 1,
                        "timestamp": datetime.now().isoformat()
                    }),
                    datetime.now()
                )
                return f"⚠️ Connection issue - saved locally for retry"
            except:
                return f"❌ Failed to process barcode {validated_barcode}"
            
    except Exception as e:
        logger.error(f"❌ Barcode processing error: {e}")
        return f"❌ Processing error: {str(e)}"

def start_plug_and_play_barcode_service():
    """Start fully automated barcode scanning service without UI"""
    logger.info("🎯 Starting Plug-and-Play Barcode Service...")
    logger.info("📱 Connect your USB barcode scanner and start scanning!")
    logger.info("🔄 System will automatically process all scanned barcodes")
    logger.info("📡 All scans sent to both Frontend API and IoT Hub")
    logger.info("⏹️  Press Ctrl+C to stop the service")
    
    try:
        while True:
            try:
         
                print("\n🎯 Ready for barcode scan (or type barcode + Enter):")
                barcode = input().strip()
                
                if barcode and len(barcode) >= 6:
                    logger.info(f"📊 Barcode scanned: {barcode}")
                    

                    result = process_barcode_scan_auto(barcode)
                    
                    if "✅" in result:
                        logger.info("✅ Barcode processed successfully")
                        print("✅ SUCCESS: Barcode sent to inventory system")
                    else:
                        logger.warning("⚠️ Barcode processing had issues")
                        print("⚠️ WARNING: Check logs for details")
                        
                else:
                    logger.warning("⚠️ Invalid barcode - please scan a valid barcode")
                    print("⚠️ Invalid barcode - try again")
                    
            except EOFError:
            
                logger.info("📱 Waiting for barcode scanner input...")
                time.sleep(1)
                continue
                
    except KeyboardInterrupt:
        logger.info("🛑 Plug-and-Play service stopped by user")
        print("\n🛑 Service stopped. Thank you for using the barcode scanner!")

def start_automatic_plug_and_play_service():
    """Start fully automatic plug-and-play barcode scanner service"""
    logger.info("🚀 Starting AUTOMATIC Plug-and-Play Barcode Scanner Service...")
    logger.info("🔌 Connect ethernet cable and USB barcode scanner")
    logger.info("📊 Just scan any barcode to test connection and auto-register!")
    logger.info("⚡ All operations are automatic - no buttons needed")
    

    connection_manager = ConnectionManager()

    device_id = get_auto_device_id()
    logger.info(f"🆔 Auto-generated Device ID: {device_id}")

    logger.info("🔄 Starting automatic unsent message processing...")
    
    try:
        while True:
            try:
                print("\n🎯 Ready for barcode scan (connect ethernet + scan barcode):")
                barcode = input().strip()
                
                if barcode and len(barcode) >= 6:
                    logger.info(f"📊 Barcode scanned: {barcode}")
                    
                    # Check ethernet connection automatically
                    ethernet_connected = check_ethernet_connection()
                    
                    if ethernet_connected:
                        logger.info("✅ Ethernet connection detected")
                        
                        # Auto-register device if not already registered
                        if not is_device_registered(device_id):
                            logger.info("📝 Auto-registering device...")
                            registration_success = auto_register_device(device_id, barcode)
                            
                            if registration_success:
                                logger.info("✅ Device auto-registered successfully!")
                                print("✅ SUCCESS: Device registered automatically")
                            else:
                                logger.warning("⚠️ Auto-registration failed, but continuing...")
                                print("⚠️ WARNING: Registration failed, check logs")
                        
                        # Process barcode automatically
                        result = process_barcode_automatically(barcode, device_id)
                        
                        if "✅" in result:
                            logger.info("✅ Barcode processed successfully")
                            print("✅ SUCCESS: Barcode sent to inventory system")
                            
                            # Auto-process any unsent messages when connection is good
                            auto_process_unsent_messages()
                        else:
                            logger.warning("⚠️ Barcode processing had issues")
                            print("⚠️ WARNING: Check logs for details")
                    else:
                        logger.warning("❌ No ethernet connection - saving locally")
                        print("❌ NO ETHERNET: Connect ethernet cable and try again")
                        
                        # Save barcode locally for retry
                        save_barcode_for_retry(barcode, device_id)
                        
                else:
                    logger.warning("⚠️ Invalid barcode - please scan a valid barcode")
                    print("⚠️ Invalid barcode - try again")
                    
            except EOFError:
                logger.info("📱 Waiting for barcode scanner input...")
                time.sleep(1)
                continue
                
    except KeyboardInterrupt:
        logger.info("🛑 Automatic service stopped by user")
        print("\n🛑 Service stopped. Thank you for using the barcode scanner!")

def get_auto_device_id():
    """Generate automatic device ID from hardware"""
    try:
        mac_address = get_local_mac_address()
        if mac_address:
            return f"auto-{mac_address.replace(':', '')[-8:]}"
        else:
            import uuid
            return f"auto-{uuid.uuid4().hex[:8]}"
    except Exception as e:
        logger.error(f"Error generating device ID: {e}")
        return f"auto-{int(time.time())}"

def check_ethernet_connection():
    """Check if ethernet connection is available"""
    try:
        from utils.network_discovery import NetworkDiscovery
        network_discovery = NetworkDiscovery()
        pi_devices = network_discovery.discover_raspberry_pi_devices()
        
        # Also check internet connectivity
        connection_manager = ConnectionManager()
        internet_connected = connection_manager.check_internet_connectivity()
        
        return len(pi_devices) > 0 or internet_connected
    except Exception as e:
        logger.error(f"Error checking ethernet connection: {e}")
        return False

def is_device_registered(device_id):
    """Check if device is already registered"""
    try:
        # Check local database
        registered_devices = local_db.get_registered_devices()
        if any(dev.get('device_id') == device_id for dev in registered_devices):
            return True
            
        # Check device manager
        if device_manager.is_device_registered(device_id):
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error checking device registration: {e}")
        return False

def auto_register_device(device_id, test_barcode):
    """Automatically register device using test barcode"""
    try:
        logger.info(f"🔧 Auto-registering device {device_id} with test barcode {test_barcode}")
        
        # Get Pi IP
        pi_ip = get_primary_raspberry_pi_ip() or "auto-detected"
        
        # Register device automatically
        device_info = {
            "registration_method": "auto_plug_and_play",
            "test_barcode": test_barcode,
            "pi_ip": pi_ip,
            "auto_registered": True
        }
        
        success, message = device_manager.register_device_without_token(device_id, device_info)
        
        if success:
            # Save locally
            local_db.save_device_registration(device_id, {
                'registration_date': datetime.now(timezone.utc).isoformat(),
                'pi_ip': pi_ip,
                'registration_method': 'auto_plug_and_play',
                'test_barcode': test_barcode
            })
            
            # SKIP API CALLS DURING REGISTRATION TO PREVENT EAN UNDEFINED DROPS
            logger.info("🚫 Skipping API registration call to prevent inventory impacts")
            logger.info("🔒 Registration completed locally and IoT Hub only")
            
            return True
        else:
            logger.error(f"❌ Auto-registration failed: {message}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Auto-registration error: {e}")
        return False

def process_barcode_automatically(barcode, device_id):
    """Process barcode automatically without UI"""
    try:
        # Validate barcode
        try:
            validated_barcode = validate_ean(barcode)
        except BarcodeValidationError:
            validated_barcode = barcode  # Accept non-EAN barcodes
        
        # Check connection
        connection_manager = ConnectionManager()
        pi_available = connection_manager.check_raspberry_pi_availability()
        
        if not pi_available:
            logger.warning("⚠️ Pi offline - saving locally for retry")
            save_barcode_for_retry(validated_barcode, device_id)
            return "⚠️ Pi offline - saved locally for retry"
        
        # Send to both API and IoT Hub
        api_success = False
        iot_success = False
        
        # Send to Frontend API
        try:
            api_result = api_client.send_barcode_scan(device_id, validated_barcode, 1)
            if api_result.get('success', False):
                api_success = True
                logger.info("✅ Sent to Frontend API successfully")
        except Exception as e:
            logger.error(f"❌ API send error: {e}")
        
        # Send to IoT Hub
        try:
            success, message = connection_manager.send_message_with_retry(
                device_id=device_id,
                barcode=validated_barcode,
                quantity=1,
                message_type="barcode_scan"
            )
            if success:
                iot_success = True
                logger.info("✅ Sent to IoT Hub successfully")
        except Exception as e:
            logger.error(f"❌ IoT Hub send error: {e}")
        
        # Return status
        if api_success and iot_success:
            return f"✅ Barcode {validated_barcode} sent to both API and IoT Hub"
        elif api_success or iot_success:
            return f"⚠️ Barcode {validated_barcode} sent partially (check logs)"
        else:
            return f"❌ Failed to send barcode {validated_barcode} (saved locally)"
            
    except Exception as e:
        logger.error(f"❌ Barcode processing error: {e}")
        return f"❌ Processing error: {str(e)}"

def save_barcode_for_retry(barcode, device_id):
    """Save barcode locally for retry when connection is restored"""
    try:
        timestamp = datetime.now(timezone.utc)
        
        # Save to local database
        local_db.save_barcode_scan(device_id, barcode, timestamp)
        
        # Save as unsent message
        message_data = {
            "deviceId": device_id,
            "barcode": barcode,
            "timestamp": timestamp.isoformat(),
            "quantity": 1,
            "messageType": "barcode_scan"
        }
        local_db.save_unsent_message(device_id, json.dumps(message_data), timestamp)
        
        logger.info(f"💾 Barcode {barcode} saved locally for retry")
        
    except Exception as e:
        logger.error(f"❌ Error saving barcode for retry: {e}")

def auto_process_unsent_messages():
    """Automatically process unsent messages when connection is good"""
    try:
        unsent_messages = local_db.get_unsent_messages()
        
        if not unsent_messages:
            return
        
        logger.info(f"🔄 Auto-processing {len(unsent_messages)} unsent messages...")
        
        connection_manager = ConnectionManager()
        processed_count = 0
        
        for message in unsent_messages[:10]:  # Process max 10 at a time
            try:
                message_data = json.loads(message.get('message', '{}'))
                device_id = message_data.get('deviceId', 'unknown')
                barcode = message_data.get('barcode', '')
                
                success, status_msg = connection_manager.send_message_with_retry(
                    device_id=device_id,
                    barcode=barcode,
                    quantity=message_data.get('quantity', 1),
                    message_type=message_data.get('messageType', 'barcode_scan')
                )
                
                if success:
                    local_db.remove_unsent_message(message['id'])
                    processed_count += 1
                    logger.info(f"✅ Auto-sent unsent message: {barcode}")
                    
            except Exception as e:
                logger.error(f"❌ Error auto-processing message: {e}")
        
        if processed_count > 0:
            logger.info(f"✅ Auto-processed {processed_count} unsent messages")
            print(f"✅ AUTO-SENT: {processed_count} previously saved barcodes")
            
    except Exception as e:
        logger.error(f"❌ Error in auto-processing unsent messages: {e}")

def main():
    """Main function with service selection menu"""
    print("🔧 Barcode Scanner Service")
    print("=" * 50)
    print("1️⃣ USB Barcode Scanner Service (Manual Entry)")
    print("2️⃣ Camera Barcode Scanner Service (Automated)")
    print("3️⃣ Gradio Web Interface")
    print("4️⃣ Test Camera Functionality")
    print("5️⃣ Scan Barcode from Image File")
    print("6️⃣ Exit")
    print("=" * 50)
    
    while True:
        try:
            choice = input("\n🎯 Select service (1-6): ").strip()
            
            if choice == "1":
                print("\n🔌 Starting USB Barcode Scanner Service...")
                start_plug_and_play_barcode_service()
                break
                
            elif choice == "2":
                print("\n📷 Starting Camera Barcode Scanner Service...")
                start_camera_barcode_service()
                break
                
            elif choice == "3":
                print("\n🌐 Starting Gradio Web Interface...")
                launch_gradio_interface()
                break
                
            elif choice == "4":
                print("\n🧪 Testing Camera Functionality...")
                test_camera_barcode_detection()
                
            elif choice == "5":
                image_path = input("📁 Enter image file path: ").strip()
                if image_path:
                    barcode = scan_barcode_from_image(image_path)
                    if barcode:
                        print(f"✅ Barcode found: {barcode}")
                        process_choice = input("🔄 Process this barcode? (y/n): ").strip().lower()
                        if process_choice == 'y':
                            result = process_barcode_scan_auto(barcode)
                            print(f"📊 Result: {result}")
                    else:
                        print("❌ No barcode found in image")
                        
            elif choice == "6":
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice. Please select 1-6.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

def test_camera_barcode_detection():
    """Test camera barcode detection functionality"""
    if not CAMERA_AVAILABLE:
        print("❌ Camera libraries not available")
        print("   Install with: pip install opencv-python pyzbar")
        return
    
    print("🧪 Testing Camera Barcode Detection")
    print("=" * 40)
    
    try:
        # Test camera initialization
        print("1️⃣ Testing camera initialization...")
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            print("✅ Camera initialized successfully")
            cap.release()
        else:
            print("❌ Camera initialization failed")
            return
        
        # Test single barcode scan
        print("\n2️⃣ Testing single barcode scan (10 seconds)...")
        print("📷 Point camera at barcode...")
        
        barcode = scan_barcode_from_camera(timeout=10)
        if barcode:
            print(f"✅ Barcode detected: {barcode}")
        else:
            print("❌ No barcode detected in 10 seconds")
        
        print("\n✅ Camera test completed")
        
    except Exception as e:
        print(f"❌ Camera test failed: {e}")

if __name__ == "__main__":
    main()