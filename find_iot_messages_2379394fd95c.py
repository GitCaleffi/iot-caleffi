#!/usr/bin/env python3
"""
IoT Hub Message Finder Guide for Device 2379394fd95c
Based on the successful test run, this guide helps locate messages in Azure portal.
"""

from datetime import datetime, timezone, timedelta

def generate_message_finder_guide():
    """Generate a comprehensive guide to find IoT Hub messages"""
    
    print("🔍 IoT HUB MESSAGE FINDER GUIDE")
    print("=" * 60)
    print("Device ID: 2379394fd95c")
    print("EAN Barcode: 7854965897485")
    print("=" * 60)
    
    # Calculate time ranges (test ran around 16:02 IST = 10:32 UTC)
    test_time_ist = datetime(2025, 9, 9, 16, 2, 0)  # IST time when test ran
    test_time_utc = test_time_ist - timedelta(hours=5, minutes=30)  # Convert to UTC
    
    print(f"\n⏰ TIME ZONE INFORMATION:")
    print(f"Test ran at: {test_time_ist.strftime('%Y-%m-%d %H:%M:%S')} IST")
    print(f"UTC equivalent: {test_time_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Azure portal shows: UTC time (not IST)")
    
    print(f"\n📍 WHERE TO LOOK IN AZURE PORTAL:")
    print("1. Go to your Azure IoT Hub in the portal")
    print("2. Navigate to: IoT devices → 2379394fd95c → Device-to-cloud messages")
    print("3. Or go to: Monitoring → Metrics → Device telemetry messages")
    
    print(f"\n🔍 SEARCH CRITERIA:")
    print(f"Device Name: 2379394fd95c")
    print(f"Time Range: {test_time_utc.strftime('%Y-%m-%d %H:%M')} to {(test_time_utc + timedelta(minutes=10)).strftime('%H:%M')} UTC")
    print(f"Message IDs to look for:")
    print(f"  - 2379394fd95c-1757413967 (registration)")
    print(f"  - 2379394fd95c-1757413971 (first quantity update)")
    print(f"  - 2379394fd95c-1757413975 (second quantity update)")
    
    print(f"\n📨 EXPECTED MESSAGE CONTENT:")
    print("Registration message:")
    print('  {"messageType": "device_registration", "deviceId": "2379394fd95c", ...}')
    print("\nQuantity update messages:")
    print('  {"messageType": "quantity_update", "barcode": "7854965897485", ...}')
    
    print(f"\n🔧 TROUBLESHOOTING STEPS:")
    print("1. Check if you're looking at the right IoT Hub instance")
    print("2. Verify time zone - Azure shows UTC, not IST (+5:30 difference)")
    print("3. Look for device '2379394fd95c' (not 'scanner-2379394fd95c')")
    print("4. Check 'Device-to-cloud messages' section specifically")
    print("5. Expand time range if needed (±30 minutes)")
    
    print(f"\n📊 MESSAGE DELIVERY CONFIRMATION:")
    print("✅ IoT Hub connection: Successful")
    print("✅ Message publishing: 'payload published for 1' (confirmed)")
    print("✅ Device registration: Created in Azure IoT Hub")
    print("✅ Message IDs generated: 3 messages sent")
    
    print(f"\n🌐 AZURE PORTAL NAVIGATION:")
    print("Portal URL: https://portal.azure.com")
    print("Path: Home → IoT Hub → [Your Hub Name] → IoT devices → 2379394fd95c")
    print("Alternative: IoT Hub → Monitoring → Logs → Device telemetry")
    
    print(f"\n⚠️ COMMON ISSUES:")
    print("• Time zone confusion (IST vs UTC)")
    print("• Looking at wrong device name")
    print("• Checking wrong IoT Hub instance")
    print("• Messages in different section than expected")
    print("• Need to refresh or wait for portal sync")
    
    print(f"\n🔄 IF STILL NOT VISIBLE:")
    print("1. Wait 2-3 minutes for portal sync")
    print("2. Try Azure CLI: az iot hub monitor-events --hub-name [hub-name]")
    print("3. Check IoT Hub logs in 'Monitoring' section")
    print("4. Verify device exists in 'IoT devices' list")

if __name__ == "__main__":
    generate_message_finder_guide()
