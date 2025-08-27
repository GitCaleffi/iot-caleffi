"""
Fast Configuration Manager - Automatic config detection and caching
Optimized for speed with minimal I/O operations and automatic detection
"""
import json
import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)

class FastConfigManager:
    """Ultra-fast configuration manager with automatic detection and caching"""
    
    def __init__(self):
        self._config_cache = None
        self._cache_timestamp = 0
        self._cache_lock = Lock()
        self._config_path = None
        self._auto_detected = False
        
        # Performance settings
        self.cache_duration = 300  # 5 minutes cache
        self.auto_refresh_enabled = True
        
        # Auto-detect config on initialization
        self._auto_detect_config()
    
    def _auto_detect_config(self) -> bool:
        """Automatically detect config.json location"""
        possible_paths = [
            # Current working directory
            Path.cwd() / "config.json",
            # Parent directory
            Path.cwd().parent / "config.json", 
            # Project root (common patterns)
            Path(__file__).parent.parent.parent / "config.json",
            # System-wide locations
            Path("/var/www/html/abhimanyu/barcode_scanner_clean/config.json"),
            Path("/etc/barcode_scanner/config.json"),
            # User home directory
            Path.home() / ".barcode_scanner" / "config.json"
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_file():
                try:
                    # Quick validation - try to parse JSON
                    with open(path, 'r') as f:
                        json.load(f)
                    
                    self._config_path = path
                    self._auto_detected = True
                    logger.info(f"✅ Auto-detected config at: {path}")
                    return True
                    
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"⚠️ Invalid config at {path}: {e}")
                    continue
        
        logger.error("❌ No valid config.json found in standard locations")
        return False
    
    def get_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """Get configuration with intelligent caching"""
        current_time = time.time()
        
        with self._cache_lock:
            # Return cached config if valid and not expired
            if (not force_reload and 
                self._config_cache is not None and 
                (current_time - self._cache_timestamp) < self.cache_duration):
                return self._config_cache
            
            # Load fresh config
            if not self._config_path:
                if not self._auto_detect_config():
                    return self._get_default_config()
            
            try:
                with open(self._config_path, 'r') as f:
                    config = json.load(f)
                
                # Update cache
                self._config_cache = config
                self._cache_timestamp = current_time
                
                return config
                
            except Exception as e:
                logger.error(f"❌ Failed to load config: {e}")
                return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return optimized default configuration"""
        return {
            "iot_hub": {
                "connection_string": "HostName=CaleffiIoT.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=5wAebNkJEH3qI3WQ8MIXMp3Yj70z68l9vAIoTMDkEyQ=",
                "use_dynamic_registration": True,
                "auto_register_devices": True
            },
            "performance": {
                "fast_mode": True,
                "cache_duration": 300,
                "parallel_processing": True,
                "batch_size": 50
            },
            "raspberry_pi": {
                "auto_detect": True,
                "status": "auto",
                "use_iot_hub_detection": False
            },
            "commercial_deployment": {
                "auto_registration": True,
                "plug_and_play": True,
                "max_devices": 10000,
                "batch_processing": True
            }
        }
    
    def get_device_connection_status(self) -> bool:
        """Automatically detect device connection status"""
        config = self.get_config()
        
        # Check if Pi status is set to auto-detect
        pi_config = config.get("raspberry_pi", {})
        pi_status = pi_config.get("status", "auto")
        
        if pi_status == "auto":
            return self._auto_detect_device_connection()
        else:
            return pi_status.lower() in ["online", "connected", "true"]
    
    def _auto_detect_device_connection(self) -> bool:
        """Fast device connection detection"""
        try:
            # Quick ping test to common Pi IP
            import subprocess
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", "192.168.1.18"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except:
            return False
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """Update configuration with automatic saving"""
        try:
            config = self.get_config()
            
            # Deep merge updates
            self._deep_merge(config, updates)
            
            # Save to file if path is available
            if self._config_path:
                with open(self._config_path, 'w') as f:
                    json.dump(config, f, indent=2)
            
            # Update cache
            with self._cache_lock:
                self._config_cache = config
                self._cache_timestamp = time.time()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update config: {e}")
            return False
    
    def _deep_merge(self, target: Dict, source: Dict) -> None:
        """Deep merge dictionaries"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
    
    def is_auto_detected(self) -> bool:
        """Check if config was auto-detected"""
        return self._auto_detected
    
    def get_config_path(self) -> Optional[Path]:
        """Get the path to the current config file"""
        return self._config_path

# Global instance for fast access
_fast_config_manager = None
_config_lock = Lock()

def get_fast_config_manager() -> FastConfigManager:
    """Get global fast config manager instance"""
    global _fast_config_manager
    
    if _fast_config_manager is None:
        with _config_lock:
            if _fast_config_manager is None:
                _fast_config_manager = FastConfigManager()
    
    return _fast_config_manager

def get_config() -> Dict[str, Any]:
    """Quick access to configuration"""
    return get_fast_config_manager().get_config()

def get_device_status() -> bool:
    """Quick access to device connection status"""
    return get_fast_config_manager().get_device_connection_status()
