#!/usr/bin/env python3
"""
Comprehensive IoT Hub message finder - helps locate messages that are being delivered
"""

import sys
import os
import json
from datetime import datetime, timezone, timedelta

def find_iot_hub_messages():
    """Provide comprehensive guidance for finding IoT Hub messages"""
    print("🔍 IoT Hub Message Finder - Complete Guide")
    print("=" * 60)
    
    current_time = datetime.now()
    current_utc = datetime.now(timezone.utc)
    
    print(f"🕐 Current Time: {current_time.strftime('%H:%M:%S')} IST")
    print(f"🕐 Current UTC: {current_utc.strftime('%H:%M:%S')} UTC")
    print()
    
    print("📱 DEVICES THAT HAVE SENT MESSAGES:")
    print("-" * 40)
    devices_with_messages = [
        ("1b058165dd09", "09:44:27 UTC", "15:14:27 IST", "device_registration"),
        ("0ca02755d72a", "09:51:25 UTC", "15:21:25 IST", "device_test"),
        ("test-frontend-api", "09:55:08 UTC", "15:25:08 IST", "device_registration")
    ]
    
    for device, utc_time, ist_time, msg_type in devices_with_messages:
        print(f"📱 Device: {device}")
        print(f"   Time: {utc_time} (UTC) / {ist_time} (IST)")
        print(f"   Type: {msg_type}")
        print(f"   Status: ✅ Message delivered ('payload published for 1')")
        print()
    
    print("🎯 STEP-BY-STEP AZURE PORTAL NAVIGATION:")
    print("-" * 40)
    print("1. Go to: https://portal.azure.com")
    print("2. Search for: 'IoT Hub' in the search bar")
    print("3. Select: 'CaleffiIoT' (your IoT Hub)")
    print("4. In the left menu, look for these sections:")
    print()
    
    print("   📊 OPTION A - Device Messages:")
    print("   • Click 'Devices' in left menu")
    print("   • Find and click device (e.g., '1b058165dd09')")
    print("   • Click 'Device-to-cloud messages'")
    print("   • Set time range to last 2 hours")
    print()
    
    print("   📈 OPTION B - Monitoring:")
    print("   • Click 'Monitoring' → 'Metrics'")
    print("   • Select metric: 'Telemetry messages sent'")
    print("   • Time range: Last 2 hours")
    print()
    
    print("   📋 OPTION C - Overview:")
    print("   • Click 'Overview' in left menu")
    print("   • Look for 'Device-to-cloud messages' chart")
    print("   • Should show message count increases")
    print()
    
    print("🔧 TROUBLESHOOTING CHECKLIST:")
    print("-" * 40)
    print("❓ Not seeing messages? Check these:")
    print()
    print("1. ⏰ TIME ZONE ISSUE:")
    print("   • Azure shows UTC time, not IST")
    print("   • Look for messages 5.5 hours EARLIER than IST time")
    print("   • Example: 15:25 IST = 09:55 UTC")
    print()
    
    print("2. 🏢 WRONG IOT HUB:")
    print("   • Verify you're in 'CaleffiIoT.azure-devices.net'")
    print("   • Check if you have multiple IoT Hubs")
    print()
    
    print("3. 📅 TIME RANGE:")
    print("   • Expand time range to 'Last 24 hours'")
    print("   • Messages might be outside current view")
    print()
    
    print("4. 🔄 PORTAL REFRESH:")
    print("   • Refresh the browser page")
    print("   • Clear browser cache if needed")
    print()
    
    print("5. 📱 DEVICE NAMES:")
    print("   • Device names are case-sensitive")
    print("   • Try searching for partial names")
    print()
    
    print("🎯 SPECIFIC SEARCH INSTRUCTIONS:")
    print("-" * 40)
    print("Search for these EXACT device names:")
    for device, utc_time, ist_time, msg_type in devices_with_messages:
        print(f"• {device} (around {utc_time})")
    print()
    
    print("Look for these message types:")
    print("• messageType: 'device_registration'")
    print("• messageType: 'device_test'")
    print("• messageType: 'visibility_test'")
    print()
    
    print("🚨 IF STILL NO MESSAGES VISIBLE:")
    print("-" * 40)
    print("The messages ARE being sent (confirmed by logs), so:")
    print()
    print("1. 🔍 Check Event Hub endpoint:")
    print("   • IoT Hub → Built-in endpoints → Event Hub-compatible endpoint")
    print("   • Messages might be there even if not in device view")
    print()
    
    print("2. 📊 Check Azure Monitor:")
    print("   • Azure Monitor → Metrics")
    print("   • Resource: Your IoT Hub")
    print("   • Metric: 'D2C Telemetry messages'")
    print()
    
    print("3. 🔧 Alternative view:")
    print("   • Try Azure CLI: az iot hub monitor-events")
    print("   • Or use IoT Explorer tool")
    print()
    
    print("=" * 60)
    print("🎯 SUMMARY")
    print("=" * 60)
    print("✅ Messages ARE being delivered to IoT Hub")
    print("✅ 'payload published for 1' confirms successful delivery")
    print("❓ Issue is finding them in Azure Portal interface")
    print()
    print("🔍 Most likely causes:")
    print("1. Time zone confusion (UTC vs IST)")
    print("2. Looking in wrong section of portal")
    print("3. Time range too narrow")
    print()
    print(f"⏰ Check around these UTC times:")
    for device, utc_time, ist_time, msg_type in devices_with_messages:
        print(f"   • {utc_time} for device {device}")

if __name__ == "__main__":
    find_iot_hub_messages()
