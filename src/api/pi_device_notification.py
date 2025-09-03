#!/usr/bin/env python3
"""
Pi Device Notification API Endpoint
Handles notifications when Pi devices connect/disconnect from the network.
"""

from flask import Flask, request, jsonify
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

def create_pi_notification_endpoint(app: Flask):
    """Add Pi device notification endpoint to Flask app"""
    
    @app.route('/api/pi-device-connected', methods=['POST'])
    def handle_pi_device_notification():
        """Handle Pi device connection/disconnection notifications"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400
            
            device_ip = data.get('device_ip')
            status = data.get('status')  # 'connected' or 'disconnected'
            timestamp = data.get('timestamp')
            device_type = data.get('device_type', 'raspberry_pi')
            
            if not device_ip or not status:
                return jsonify({'error': 'Missing device_ip or status'}), 400
            
            # Log the notification
            if status == 'connected':
                logger.info(f"🟢 Pi device connected notification: {device_ip}")
            else:
                logger.info(f"🔴 Pi device disconnected notification: {device_ip}")
            
            # Update system state
            _update_system_pi_status(device_ip, status, timestamp)
            
            # Trigger barcode scanner refresh
            _refresh_barcode_scanner()
            
            return jsonify({
                'status': 'success',
                'message': f'Pi device {status} notification processed',
                'device_ip': device_ip,
                'processed_at': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error processing Pi notification: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/pi-devices', methods=['GET'])
    def get_pi_devices():
        """Get list of currently connected Pi devices"""
        try:
            # Get devices from dynamic discovery
            from utils.dynamic_pi_discovery import DynamicPiDiscovery
            from utils.config import load_config
            
            config = load_config()
            discovery = DynamicPiDiscovery(config)
            devices = discovery.get_current_devices()
            
            return jsonify({
                'devices': devices,
                'count': len(devices),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting Pi devices: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/pi-devices/scan', methods=['POST'])
    def force_pi_scan():
        """Force an immediate Pi device scan"""
        try:
            from utils.dynamic_pi_discovery import DynamicPiDiscovery
            from utils.config import load_config
            
            config = load_config()
            discovery = DynamicPiDiscovery(config)
            devices = discovery.force_scan()
            
            return jsonify({
                'status': 'scan_completed',
                'devices': devices,
                'count': len(devices),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error forcing Pi scan: {e}")
            return jsonify({'error': str(e)}), 500

def _update_system_pi_status(device_ip: str, status: str, timestamp: str):
    """Update system configuration with Pi device status"""
    try:
        from utils.config import load_config, save_config
        
        config = load_config()
        pi_config = config.get("raspberry_pi", {})
        
        if status == 'connected':
            pi_config["auto_detected_ip"] = device_ip
            pi_config["last_detection"] = timestamp or datetime.now().isoformat()
            pi_config["status"] = "connected"
        else:
            if pi_config.get("auto_detected_ip") == device_ip:
                pi_config["auto_detected_ip"] = None
                pi_config["status"] = "disconnected"
        
        config["raspberry_pi"] = pi_config
        save_config(config)
        
        logger.info(f"✅ System config updated: Pi {status} at {device_ip}")
        
    except Exception as e:
        logger.error(f"Error updating system Pi status: {e}")

def _refresh_barcode_scanner():
    """Trigger barcode scanner system refresh"""
    try:
        # Import here to avoid circular imports
        from barcode_scanner_app import refresh_pi_connection
        
        refresh_pi_connection()
        logger.info("🔄 Barcode scanner system refreshed")
        
    except Exception as e:
        logger.error(f"Error refreshing barcode scanner: {e}")
