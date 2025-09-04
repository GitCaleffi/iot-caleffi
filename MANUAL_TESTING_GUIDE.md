# Manual Testing Guide - Plug-and-Play Barcode Scanner

This guide provides step-by-step manual testing procedures for the automatic plug-and-play barcode scanner system.

## Prerequisites

1. **Hardware Setup:**
   - Raspberry Pi with ethernet port
   - USB barcode scanner
   - Ethernet cable
   - Internet connection available

2. **Software Setup:**
   - Ensure all dependencies are installed: `pip install -r requirements-device.txt`
   - Verify config.json is properly configured
   - Check that the database is accessible

## Test Categories

### 1. Basic System Startup Test

**Objective:** Verify the automatic service starts correctly

**Commands:**
```bash
# Navigate to the deployment directory
cd /var/www/html/abhimanyu/barcode_scanner_clean/deployment_package

# Start the automatic plug-and-play service
python src/barcode_scanner_app.py

# Expected Output:
# 🚀 Starting AUTOMATIC Plug-and-Play Barcode Scanner Service...
# 🔌 Connect ethernet cable and USB barcode scanner
# 📊 Just scan any barcode to test connection and auto-register!
# ⚡ All operations are automatic - no buttons needed
# 🆔 Auto-generated Device ID: [device_id]
# 🔄 Starting automatic unsent message processing...
# 🎯 Ready for barcode scan (connect ethernet + scan barcode):
```

**Verification:**
- Service starts without errors
- Device ID is auto-generated
- Console shows ready state for barcode input

---

### 2. Ethernet Connection Detection Test

**Objective:** Test automatic ethernet connection detection

**Test 2.1: With Ethernet Connected**
```bash
# With ethernet cable connected, run connection test
python -c "
from src.utils.connection_manager import ConnectionManager
from src.barcode_scanner_app import check_ethernet_connection
cm = ConnectionManager()
print('Ethernet Status:', check_ethernet_connection())
print('Internet Status:', cm.check_internet_connectivity())
"

# Expected Output:
# Ethernet Status: True
# Internet Status: True
```

**Test 2.2: Without Ethernet Connected**
```bash
# Disconnect ethernet cable, then run test
python -c "
from src.utils.connection_manager import ConnectionManager
from src.barcode_scanner_app import check_ethernet_connection
cm = ConnectionManager()
print('Ethernet Status:', check_ethernet_connection())
print('Internet Status:', cm.check_internet_connectivity())
"

# Expected Output:
# Ethernet Status: False
# Internet Status: False
```

---

### 3. Device Auto-Registration Test

**Objective:** Test automatic device registration on first barcode scan

**Test 3.1: Fresh Device Registration**
```bash
# Clear any existing device registration
python -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
db.execute_query('DELETE FROM device_registrations')
print('Device registrations cleared')
"

# Start the service and scan a barcode
python src/barcode_scanner_app.py
# When prompted, scan any valid barcode (e.g., 1234567890123)

# Expected Console Output:
# 📊 Barcode scanned: 1234567890123
# ✅ Ethernet connection detected
# 📝 Auto-registering device...
# ✅ Device auto-registered successfully!
# ✅ SUCCESS: Device registered automatically
# ✅ SUCCESS: Barcode sent to inventory system
```

**Test 3.2: Verify Registration in Database**
```bash
# Check device registration was saved
python -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
registrations = db.fetch_all('SELECT * FROM device_registrations')
print('Registered devices:', registrations)
"

# Expected Output:
# Registered devices: [('device_id', 'timestamp', 'status')]
```

---

### 4. Barcode Processing Test

**Objective:** Test automatic barcode processing and sending

**Test 4.1: Valid Barcode Processing**
```bash
# With device already registered and ethernet connected
python src/barcode_scanner_app.py
# Scan a valid EAN barcode (e.g., 8901030895559)

# Expected Console Output:
# 📊 Barcode scanned: 8901030895559
# ✅ Ethernet connection detected
# ✅ SUCCESS: Barcode sent to inventory system
```

**Test 4.2: Invalid Barcode Handling**
```bash
# Scan an invalid barcode (less than 6 characters)
# Input: 123

# Expected Console Output:
# ⚠️ Invalid barcode - try again
```

**Test 4.3: Verify Barcode in Database**
```bash
# Check barcode was saved to database
python -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
scans = db.fetch_all('SELECT * FROM barcode_scans ORDER BY timestamp DESC LIMIT 5')
print('Recent barcode scans:', scans)
"
```

---

### 5. Offline Mode Test

**Objective:** Test behavior when ethernet is disconnected

**Test 5.1: Offline Barcode Scanning**
```bash
# Disconnect ethernet cable
# Start service and scan a barcode
python src/barcode_scanner_app.py
# Scan barcode: 1234567890123

# Expected Console Output:
# 📊 Barcode scanned: 1234567890123
# ❌ NO ETHERNET: Connect ethernet cable and try again
```

**Test 5.2: Verify Offline Storage**
```bash
# Check that barcode was saved for retry
python -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
unsent = db.fetch_all('SELECT * FROM unsent_messages ORDER BY timestamp DESC LIMIT 5')
print('Unsent messages:', unsent)
"

# Expected Output:
# Unsent messages: [('message_id', 'barcode', 'timestamp', 'retry_count')]
```

---

### 6. Auto-Recovery Test

**Objective:** Test automatic processing of unsent messages when connection is restored

**Test 6.1: Connection Recovery**
```bash
# With unsent messages in database, reconnect ethernet
# Start service and scan any barcode
python src/barcode_scanner_app.py
# Scan barcode: 9876543210987

# Expected Console Output:
# 📊 Barcode scanned: 9876543210987
# ✅ Ethernet connection detected
# ✅ SUCCESS: Barcode sent to inventory system
# (Auto-processing of unsent messages happens in background)
```

**Test 6.2: Verify Unsent Messages Cleared**
```bash
# Check that unsent messages were processed
python -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
unsent = db.fetch_all('SELECT * FROM unsent_messages')
print('Remaining unsent messages:', len(unsent))
"

# Expected Output:
# Remaining unsent messages: 0
```

---

### 7. Connection Manager Test

**Objective:** Test connection manager functionality

**Test 7.1: Connection Status Check**
```bash
python -c "
from src.utils.connection_manager import ConnectionManager
cm = ConnectionManager()
print('Internet connectivity:', cm.check_internet_connectivity())
print('LAN Pi detection:', cm.check_lan_pi_connection())
print('Connection status:', cm.get_connection_status())
"
```

**Test 7.2: Network Discovery**
```bash
python -c "
from src.utils.connection_manager import ConnectionManager
cm = ConnectionManager()
devices = cm.discover_network_devices()
print('Network devices found:', len(devices))
for device in devices[:3]:  # Show first 3
    print(f'  - {device}')
"
```

---

### 8. Database Operations Test

**Objective:** Test database functionality

**Test 8.1: Database Connection**
```bash
python -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
print('Database connection successful')
tables = db.fetch_all(\"SELECT name FROM sqlite_master WHERE type='table'\")
print('Available tables:', [table[0] for table in tables])
"
```

**Test 8.2: Database Queries**
```bash
# Check recent activity
python -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
print('Recent barcode scans:')
scans = db.fetch_all('SELECT barcode, timestamp FROM barcode_scans ORDER BY timestamp DESC LIMIT 3')
for scan in scans:
    print(f'  {scan[0]} at {scan[1]}')
    
print('Device registrations:')
regs = db.fetch_all('SELECT device_id, registration_date FROM device_registrations')
for reg in regs:
    print(f'  {reg[0]} registered on {reg[1]}')
"
```

---

### 9. Error Handling Test

**Objective:** Test system behavior under error conditions

**Test 9.1: Invalid Configuration**
```bash
# Backup current config
cp config.json config.json.backup

# Create invalid config
echo '{"invalid": "config"}' > config.json

# Try to start service
python src/barcode_scanner_app.py

# Expected: Graceful error handling with informative message

# Restore config
mv config.json.backup config.json
```

**Test 9.2: Database Lock Test**
```bash
# Test concurrent access
python -c "
import threading
import time
from src.database.db_manager import DatabaseManager

def test_db_access(thread_id):
    db = DatabaseManager()
    for i in range(3):
        try:
            result = db.fetch_all('SELECT COUNT(*) FROM barcode_scans')
            print(f'Thread {thread_id}: Query {i+1} successful')
            time.sleep(0.1)
        except Exception as e:
            print(f'Thread {thread_id}: Error - {e}')

# Start multiple threads
threads = []
for i in range(3):
    t = threading.Thread(target=test_db_access, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
    
print('Concurrent database access test completed')
"
```

---

### 10. Performance Test

**Objective:** Test system performance under load

**Test 10.1: Rapid Barcode Scanning**
```bash
# Test rapid barcode processing
python -c "
import time
from src.barcode_scanner_app import process_barcode_automatically, get_auto_device_id

device_id = get_auto_device_id()
test_barcodes = ['1234567890123', '2345678901234', '3456789012345', '4567890123456', '5678901234567']

start_time = time.time()
for i, barcode in enumerate(test_barcodes):
    print(f'Processing barcode {i+1}: {barcode}')
    result = process_barcode_automatically(barcode, device_id)
    print(f'Result: {result[:50]}...')
    
end_time = time.time()
print(f'Processed {len(test_barcodes)} barcodes in {end_time - start_time:.2f} seconds')
"
```

---

## Test Results Verification

### Success Criteria

1. **Service Startup:** Service starts without errors and shows ready state
2. **Connection Detection:** Correctly detects ethernet and internet status
3. **Auto-Registration:** Device registers automatically on first barcode scan
4. **Barcode Processing:** Valid barcodes are processed and sent successfully
5. **Offline Handling:** Invalid network conditions are handled gracefully
6. **Auto-Recovery:** Unsent messages are processed when connection is restored
7. **Database Operations:** All database operations complete successfully
8. **Error Handling:** System handles errors gracefully without crashing

### Troubleshooting Commands

```bash
# Check system logs
tail -f /var/log/syslog | grep barcode

# Check application logs
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Run any test command here
"

# Check network interfaces
ip addr show
ping -c 3 8.8.8.8

# Check USB devices (for barcode scanner)
lsusb

# Check running processes
ps aux | grep python
```

### Clean-up Commands

```bash
# Reset device registration
python -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
db.execute_query('DELETE FROM device_registrations')
print('Device registrations cleared')
"

# Clear unsent messages
python -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
db.execute_query('DELETE FROM unsent_messages')
print('Unsent messages cleared')
"

# Clear barcode scans (optional)
python -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
db.execute_query('DELETE FROM barcode_scans')
print('Barcode scans cleared')
"
```

## Notes

- All tests should be run from the deployment_package directory
- Ensure proper permissions for database and config files
- Monitor system resources during performance tests
- Keep ethernet cable and barcode scanner readily available for testing
- Document any unexpected behavior or errors encountered
