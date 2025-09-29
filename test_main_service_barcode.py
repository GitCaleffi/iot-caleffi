#!/usr/bin/env python3
"""
Test if main service can detect barcode scans
"""

import subprocess
import time
import os

def test_main_service():
    """Test main service barcode detection"""
    
    print("🔍 Testing Main Service Barcode Detection")
    print("=" * 45)
    
    print("📱 Please scan a barcode now...")
    print("⏰ Monitoring service logs for 30 seconds...")
    
    # Monitor service logs in real-time
    try:
        process = subprocess.Popen(
            ['journalctl', '-u', 'caleffi-barcode-scanner.service', '-f', '--no-pager'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        start_time = time.time()
        barcode_detected = False
        
        while time.time() - start_time < 30:  # 30 seconds
            line = process.stdout.readline()
            if line:
                print(f"📝 {line.strip()}")
                
                # Check for barcode-related messages
                if any(keyword in line.lower() for keyword in ['barcode', 'scan', 'detected', 'processed']):
                    barcode_detected = True
                    print("✅ Barcode activity detected in service!")
            
            time.sleep(0.1)
        
        process.terminate()
        
        if barcode_detected:
            print("\n✅ Main service is detecting barcodes!")
            return True
        else:
            print("\n❌ No barcode activity detected in main service")
            return False
            
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted")
        return False
    except Exception as e:
        print(f"\n❌ Error monitoring service: {e}")
        return False

def check_pos_output():
    """Check if POS output file is created"""
    
    print("\n📄 Checking POS Output:")
    
    pos_files = [
        "/tmp/pos_barcode.txt",
        "/var/log/pos_output.log",
        "/tmp/barcode_output.txt"
    ]
    
    for pos_file in pos_files:
        if os.path.exists(pos_file):
            print(f"✅ Found POS output: {pos_file}")
            try:
                with open(pos_file, 'r') as f:
                    lines = f.readlines()
                print(f"📊 Contains {len(lines)} entries")
                if lines:
                    print("📝 Recent entries:")
                    for line in lines[-3:]:
                        print(f"  {line.strip()}")
                return True
            except Exception as e:
                print(f"❌ Error reading {pos_file}: {e}")
        else:
            print(f"⚠️  {pos_file} not found")
    
    return False

if __name__ == "__main__":
    print("🚀 Main Service Barcode Test")
    print("=" * 35)
    
    # Test 1: Monitor service logs
    service_working = test_main_service()
    
    # Test 2: Check POS output
    pos_working = check_pos_output()
    
    print(f"\n📊 Results:")
    print(f"  Service Detection: {'✅ WORKING' if service_working else '❌ NOT WORKING'}")
    print(f"  POS Output: {'✅ WORKING' if pos_working else '❌ NOT WORKING'}")
    
    if not service_working:
        print(f"\n🔧 Troubleshooting:")
        print(f"  1. Service may not be monitoring the correct input device")
        print(f"  2. Input device permissions might be blocking access")
        print(f"  3. Service might need restart to detect new USB device")
        
        print(f"\n💡 Try restarting the service:")
        print(f"  sudo systemctl restart caleffi-barcode-scanner.service")
