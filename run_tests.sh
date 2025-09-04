#!/bin/bash

# Test Runner Script for Plug-and-Play Barcode Scanner
# Provides easy access to both manual and automated testing

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if we're in the right directory
    if [ ! -f "deployment_package/src/barcode_scanner_app.py" ]; then
        print_error "Please run this script from the project root directory"
        exit 1
    fi
    
    # Check Python installation
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 is not installed"
        exit 1
    fi
    
    # Check if requirements are installed
    if [ -f "requirements-device.txt" ]; then
        print_status "Installing/checking requirements..."
        pip3 install -r requirements-device.txt > /dev/null 2>&1 || {
            print_warning "Some requirements may not be installed properly"
        }
    fi
    
    print_success "Prerequisites check completed"
}

# Function to run automated tests
run_automated_tests() {
    print_status "Running automated test suite..."
    echo "=================================="
    
    if python3 test_automation.py; then
        print_success "All automated tests passed!"
        return 0
    else
        print_error "Some automated tests failed"
        return 1
    fi
}

# Function to run specific manual test
run_manual_test() {
    local test_name="$1"
    print_status "Running manual test: $test_name"
    
    case "$test_name" in
        "connection")
            print_status "Testing connection detection..."
            cd deployment_package
            python3 -c "
from src.utils.connection_manager import ConnectionManager
from src.barcode_scanner_app import check_ethernet_connection
cm = ConnectionManager()
print('Ethernet Status:', check_ethernet_connection())
print('Internet Status:', cm.check_internet_connectivity())
print('LAN Pi Status:', cm.check_lan_pi_connection())
"
            ;;
        "database")
            print_status "Testing database operations..."
            cd deployment_package
            python3 -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()
print('Database connection successful')
tables = db.fetch_all(\"SELECT name FROM sqlite_master WHERE type='table'\")
print('Available tables:', [table[0] for table in tables])
scans = db.fetch_all('SELECT COUNT(*) FROM barcode_scans')
print('Total barcode scans:', scans[0][0] if scans else 0)
"
            ;;
        "device-id")
            print_status "Testing device ID generation..."
            cd deployment_package
            python3 -c "
from src.barcode_scanner_app import get_auto_device_id
device_id = get_auto_device_id()
print('Generated Device ID:', device_id)
print('Device ID length:', len(device_id))
"
            ;;
        "registration")
            print_status "Testing device registration status..."
            cd deployment_package
            python3 -c "
from src.barcode_scanner_app import get_auto_device_id, is_device_registered
from src.database.db_manager import DatabaseManager
device_id = get_auto_device_id()
print('Device ID:', device_id)
print('Is Registered:', is_device_registered(device_id))
db = DatabaseManager()
regs = db.fetch_all('SELECT device_id, registration_date FROM device_registrations')
print('All registered devices:', len(regs))
for reg in regs:
    print(f'  - {reg[0]} (registered: {reg[1]})')
"
            ;;
        *)
            print_error "Unknown manual test: $test_name"
            print_status "Available manual tests: connection, database, device-id, registration"
            return 1
            ;;
    esac
}

# Function to show system status
show_system_status() {
    print_status "System Status Check"
    echo "==================="
    
    # Network interfaces
    print_status "Network Interfaces:"
    ip addr show | grep -E "^[0-9]+:|inet " | head -10
    
    # USB devices (for barcode scanner)
    print_status "USB Devices:"
    lsusb | head -5
    
    # Disk space
    print_status "Disk Space:"
    df -h . | tail -1
    
    # Python processes
    print_status "Python Processes:"
    ps aux | grep python | grep -v grep | head -3
    
    # Database file
    if [ -f "deployment_package/barcode_scanner.db" ]; then
        print_status "Database file exists ($(du -h deployment_package/barcode_scanner.db | cut -f1))"
    else
        print_warning "Database file not found"
    fi
    
    # Config file
    if [ -f "config.json" ]; then
        print_status "Config file exists"
    else
        print_warning "Config file not found"
    fi
}

# Function to clean test data
clean_test_data() {
    print_status "Cleaning test data..."
    
    cd deployment_package
    python3 -c "
from src.database.db_manager import DatabaseManager
db = DatabaseManager()

# Clean test data
db.execute_query('DELETE FROM barcode_scans WHERE barcode LIKE \"TEST%\" OR barcode LIKE \"PERF%\" OR barcode LIKE \"CONCURRENT%\"')
db.execute_query('DELETE FROM device_registrations WHERE device_id LIKE \"TEST_%\"')
db.execute_query('DELETE FROM unsent_messages WHERE message_data LIKE \"%TEST%\"')

print('Test data cleaned successfully')
"
    
    print_success "Test data cleanup completed"
}

# Function to start interactive service
start_service() {
    print_status "Starting Plug-and-Play Barcode Scanner Service..."
    print_warning "Press Ctrl+C to stop the service"
    echo ""
    
    cd deployment_package
    python3 src/barcode_scanner_app.py
}

# Function to show help
show_help() {
    echo "Plug-and-Play Barcode Scanner Test Runner"
    echo "========================================"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  auto                    Run automated test suite"
    echo "  manual <test_name>      Run specific manual test"
    echo "  status                  Show system status"
    echo "  clean                   Clean test data from database"
    echo "  start                   Start the barcode scanner service"
    echo "  help                    Show this help message"
    echo ""
    echo "Manual Tests:"
    echo "  connection              Test network connection detection"
    echo "  database                Test database operations"
    echo "  device-id               Test device ID generation"
    echo "  registration            Test device registration status"
    echo ""
    echo "Examples:"
    echo "  $0 auto                 # Run all automated tests"
    echo "  $0 manual connection    # Test connection detection"
    echo "  $0 status               # Show system status"
    echo "  $0 start                # Start the service"
}

# Main script logic
main() {
    case "${1:-help}" in
        "auto")
            check_prerequisites
            run_automated_tests
            ;;
        "manual")
            if [ -z "$2" ]; then
                print_error "Please specify a manual test name"
                show_help
                exit 1
            fi
            check_prerequisites
            run_manual_test "$2"
            ;;
        "status")
            show_system_status
            ;;
        "clean")
            check_prerequisites
            clean_test_data
            ;;
        "start")
            check_prerequisites
            start_service
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
