#!/usr/bin/env python3
"""
Test script for Device Manager functionality
"""
import sys
import os
import time
import json
import logging
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('device_manager_test.log')
    ]
)

logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from file"""
    # Try multiple possible config locations
    possible_paths = [
        os.path.join(os.path.dirname(__file__), 'config.json'),
        os.path.join(os.path.dirname(__file__), 'src', 'config.json'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    ]
    
    for config_path in possible_paths:
        try:
            with open(config_path, 'r') as f:
                logger.info(f"Loading config from: {config_path}")
                config = json.load(f)
                # Ensure required IoT Hub config exists
                if 'iot_hub' not in config:
                    config['iot_hub'] = {}
                return config
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file {config_path}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            continue
    
    logger.warning("No valid config file found, using default config")
    return {
        'iot_hub': {
            'connection_string': os.getenv('IOT_HUB_CONNECTION_STRING', ''),
            'device_registry_url': os.getenv('IOT_HUB_REGISTRY_URL', ''),
            'api_key': os.getenv('IOT_HUB_API_KEY', '')
        }
    }

def test_device_manager():
    """Test the Device Manager functionality"""
    from src.services.device_manager import DeviceManager
    
    logger.info("=== Starting Device Manager Test ===")
    
    # Load config
    config = load_config()
    
    # Initialize device manager
    try:
        logger.info("Initializing Device Manager...")
        device_manager = DeviceManager(config)
        
        # Let it run for a while
        logger.info("Running for 2 minutes (press Ctrl+C to exit early)...")
        
        start_time = time.time()
        while time.time() - start_time < 120:  # Run for 2 minutes
            status = device_manager.get_status()
            logger.info(f"Status: {json.dumps(status, indent=2)}")
            time.sleep(10)
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        try:
            device_manager.shutdown()
        except:
            pass
        
    logger.info("=== Device Manager Test Complete ===")

if __name__ == "__main__":
    try:
        test_device_manager()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise
