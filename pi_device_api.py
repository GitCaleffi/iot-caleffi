#!/usr/bin/env python3
"""
Pi Device API Endpoints - Add to live server web_app.py
Handles Pi device registration and heartbeat from remote Pi devices
"""

from flask import request, jsonify
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# Add these endpoints to your live server web_app.py

@app.route('/api/pi-device-register', methods=['POST'])
def pi_device_register():
    """Register a Pi device from remote location"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        device_id = data.get('device_id', 'unknown')
        mac_address = data.get('mac_address', 'unknown')
        ip_address = data.get('ip_address', 'unknown')
        
        # Store device registration in database
        local_storage = LocalStorage()
        conn = sqlite3.connect(local_storage.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS available_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT UNIQUE,
            device_name TEXT,
            ip_address TEXT,
            mac_address TEXT,
            device_type TEXT,
            status TEXT DEFAULT 'online',
            registered_at TEXT,
            last_seen TEXT
        )
        """)
        
        cursor.execute("""
        INSERT OR REPLACE INTO available_devices 
        (device_id, device_name, ip_address, mac_address, device_type, status, registered_at, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            device_id, f"Pi-{mac_address[-8:]}", ip_address, mac_address, "raspberry_pi",
            'online', datetime.now().isoformat(), datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Registered Pi device: {device_id} at {ip_address}")
        
        return jsonify({
            "status": "success",
            "message": "Device registered successfully",
            "device_id": device_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error in pi_device_register: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pi-device-heartbeat', methods=['POST'])
def pi_device_heartbeat():
    """Receive heartbeat from Pi device"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        ip_address = data.get('ip_address')
        
        if not device_id:
            return jsonify({"error": "Device ID required"}), 400
        
        # Update device status
        local_storage = LocalStorage()
        conn = sqlite3.connect(local_storage.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE available_devices SET status = ?, last_seen = ?, ip_address = ? WHERE device_id = ?",
            ['online', datetime.now().isoformat(), ip_address, device_id]
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Error in pi_device_heartbeat: {e}")
        return jsonify({"error": str(e)}), 500