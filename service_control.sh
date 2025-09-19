#!/bin/bash
# service_control.sh - Black Box Barcode Scanner Service Control

# Define project variables
PROJECT_DIR="/var/www/html/abhimanyu/barcode_scanner_clean"
SERVICE_NAME="barcode-scanner"
SCRIPT_PATH="$PROJECT_DIR/keyboard_scanner.py"
LOG_PATH="$PROJECT_DIR/scanner.log"

show_usage() {
    echo "🔧 Barcode Scanner Service Control"
    echo "=================================="
    echo "📁 Project: $PROJECT_DIR"
    echo "🔧 Service: $SERVICE_NAME"
    echo ""
    echo "Usage: $0 {start|stop|restart|status|logs|install|uninstall}"
    echo ""
    echo "Commands:"
    echo "  start     - Start the barcode scanner service"
    echo "  stop      - Stop the barcode scanner service"
    echo "  restart   - Restart the barcode scanner service"
    echo "  status    - Show service status"
    echo "  logs      - Show service logs (live)"
    echo "  install   - Install and enable the service"
    echo "  uninstall - Remove the service"
    echo ""
}

case "$1" in
    start)
        echo "🚀 Starting barcode scanner service..."
        sudo systemctl start $SERVICE_NAME
        sleep 2
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    stop)
        echo "🛑 Stopping barcode scanner service..."
        sudo systemctl stop $SERVICE_NAME
        sleep 2
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    restart)
        echo "🔄 Restarting barcode scanner service..."
        sudo systemctl restart $SERVICE_NAME
        sleep 2
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    status)
        echo "📊 Barcode scanner service status:"
        echo "=================================="
        sudo systemctl status $SERVICE_NAME --no-pager
        echo ""
        echo "📋 Process information:"
        ps aux | grep keyboard_scanner | grep -v grep || echo "Service not running"
        echo ""
        echo "📁 Log file size:"
        if [ -f "$LOG_PATH" ]; then
            ls -lh "$LOG_PATH"
        else
            echo "Log file not found at $LOG_PATH"
        fi
        ;;
    logs)
        echo "📊 Showing live service logs (Ctrl+C to exit):"
        echo "=============================================="
        echo "📁 Project: $PROJECT_DIR"
        echo "📝 Log file: $LOG_PATH"
        echo ""
        echo "🔍 System logs:"
        sudo journalctl -u $SERVICE_NAME -f &
        JOURNAL_PID=$!
        echo ""
        echo "📝 Application logs:"
        if [ -f "$LOG_PATH" ]; then
            tail -f "$LOG_PATH" &
            TAIL_PID=$!
        fi
        
        # Wait for Ctrl+C
        trap "kill $JOURNAL_PID $TAIL_PID 2>/dev/null; exit" INT
        wait
        ;;
    install)
        echo "📦 Installing barcode scanner service..."
        $PROJECT_DIR/setup_automation.sh
        ;;
    uninstall)
        echo "🗑️ Uninstalling barcode scanner service..."
        sudo systemctl stop $SERVICE_NAME 2>/dev/null
        sudo systemctl disable $SERVICE_NAME 2>/dev/null
        sudo rm -f /etc/systemd/system/$SERVICE_NAME.service
        sudo systemctl daemon-reload
        crontab -l 2>/dev/null | grep -v "launcher.sh" | crontab -
        echo "✅ Service uninstalled"
        ;;
    *)
        show_usage
        exit 1
        ;;
esac