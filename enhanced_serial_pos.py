#!/usr/bin/env python3
"""
Enhanced Serial POS Communication for Pi 5
Direct serial communication with POS terminals
"""

import os
import sys
import time
import logging
import serial
import glob
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedSerialPOS:
    def __init__(self):
        self.working_ports = self._detect_working_serial_ports()
        self.pos_configs = self._get_pos_configurations()
        
    def _detect_working_serial_ports(self) -> List[str]:
        """Detect working serial ports for POS communication"""
        logger.info("🔍 Detecting working serial ports for POS...")
        
        working_ports = []
        
        # Test known working ports from your system
        test_ports = ['/dev/ttyS0', '/dev/ttyS4']
        
        # Also check for USB-Serial adapters
        usb_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        test_ports.extend(usb_ports)
        
        for port in test_ports:
            if os.path.exists(port) and self._test_serial_port(port):
                working_ports.append(port)
                logger.info(f"✅ Working serial port found: {port}")
        
        logger.info(f"📊 Total working serial ports: {len(working_ports)}")
        return working_ports
    
    def _test_serial_port(self, port: str) -> bool:
        """Test if serial port is accessible and working"""
        try:
            with serial.Serial(port, 9600, timeout=0.5) as ser:
                return True
        except Exception as e:
            if "Input/output error" not in str(e):
                logger.debug(f"Port {port} test failed: {e}")
            return False
    
    def _get_pos_configurations(self) -> List[Dict]:
        """Get common POS terminal configurations"""
        return [
            {
                'name': 'Standard POS',
                'baud_rate': 9600,
                'data_bits': 8,
                'parity': 'N',
                'stop_bits': 1,
                'format': '{barcode}\r\n'
            },
            {
                'name': 'Receipt Printer',
                'baud_rate': 9600,
                'data_bits': 8,
                'parity': 'N', 
                'stop_bits': 1,
                'format': 'SCAN:{barcode}\r\n'
            },
            {
                'name': 'Cash Register',
                'baud_rate': 19200,
                'data_bits': 8,
                'parity': 'N',
                'stop_bits': 1,
                'format': '{barcode}\n'
            },
            {
                'name': 'Legacy Terminal',
                'baud_rate': 2400,
                'data_bits': 7,
                'parity': 'E',
                'stop_bits': 1,
                'format': '{barcode}\r'
            }
        ]
    
    def send_barcode_to_pos(self, barcode: str) -> Dict[str, bool]:
        """Send barcode to all working POS terminals"""
        logger.info(f"📤 Sending barcode {barcode} to {len(self.working_ports)} POS terminal(s)")
        
        results = {}
        
        for port in self.working_ports:
            port_results = []
            
            # Try different POS configurations for each port
            for config in self.pos_configs:
                success = self._send_to_port_with_config(barcode, port, config)
                port_results.append(success)
                
                if success:
                    logger.info(f"✅ {port} - {config['name']} format successful")
                    break  # Stop trying other configs for this port
                else:
                    logger.debug(f"⚠️ {port} - {config['name']} format failed")
            
            # Port is successful if any config worked
            results[f'SERIAL_{port}'] = any(port_results)
        
        # Summary
        successful = [k for k, v in results.items() if v]
        failed = [k for k, v in results.items() if not v]
        
        logger.info(f"📊 POS Communication Results:")
        if successful:
            logger.info(f"  ✅ Successful: {', '.join(successful)}")
        if failed:
            logger.info(f"  ❌ Failed: {', '.join(failed)}")
        
        return results
    
    def _send_to_port_with_config(self, barcode: str, port: str, config: Dict) -> bool:
        """Send barcode to specific port with specific configuration"""
        try:
            # Format barcode according to POS configuration
            formatted_barcode = config['format'].format(barcode=barcode)
            
            # Configure serial connection
            ser_config = {
                'port': port,
                'baudrate': config['baud_rate'],
                'bytesize': config['data_bits'],
                'parity': config['parity'],
                'stopbits': config['stop_bits'],
                'timeout': 2,
                'write_timeout': 2
            }
            
            with serial.Serial(**ser_config) as ser:
                # Send formatted barcode
                ser.write(formatted_barcode.encode())
                ser.flush()
                
                # Small delay for POS processing
                time.sleep(0.1)
                
                # Try to read response (some POS terminals send ACK)
                try:
                    response = ser.read(10)
                    if response:
                        logger.debug(f"POS response from {port}: {response}")
                except:
                    pass  # No response is normal for many POS terminals
            
            return True
            
        except Exception as e:
            logger.debug(f"Serial send failed {port} ({config['name']}): {e}")
            return False
    
    def send_barcode_optimized(self, barcode: str) -> bool:
        """Optimized barcode sending - uses best known configuration first"""
        logger.info(f"🚀 Optimized POS send: {barcode}")
        
        if not self.working_ports:
            logger.warning("⚠️ No working serial ports available")
            return False
        
        # Use the first working port with standard configuration
        port = self.working_ports[0]
        standard_config = self.pos_configs[0]  # Standard POS config
        
        success = self._send_to_port_with_config(barcode, port, standard_config)
        
        if success:
            logger.info(f"✅ Optimized send successful to {port}")
        else:
            logger.warning(f"⚠️ Optimized send failed, trying all configurations...")
            # Fallback to trying all configurations
            results = self.send_barcode_to_pos(barcode)
            success = any(results.values())
        
        return success
    
    def test_pos_communication(self, test_barcode: str = "TEST123456789") -> Dict[str, bool]:
        """Test POS communication with all configurations"""
        logger.info(f"🧪 Testing POS communication with: {test_barcode}")
        
        results = self.send_barcode_to_pos(test_barcode)
        
        # Summary
        total_ports = len(self.working_ports)
        successful_ports = sum(1 for success in results.values() if success)
        
        logger.info(f"\n📊 POS Test Summary:")
        logger.info(f"  Working serial ports: {total_ports}")
        logger.info(f"  Successful communications: {successful_ports}")
        logger.info(f"  Success rate: {successful_ports/total_ports*100:.1f}%" if total_ports > 0 else "  Success rate: 0%")
        
        return results

# Global instance
_serial_pos = None

def get_serial_pos():
    """Get global serial POS instance"""
    global _serial_pos
    if _serial_pos is None:
        _serial_pos = EnhancedSerialPOS()
    return _serial_pos

def main():
    """Test the enhanced serial POS communication"""
    print("🔌 Enhanced Serial POS Communication for Pi 5")
    print("=" * 50)
    
    pos_comm = EnhancedSerialPOS()
    
    # Test with sample barcode
    test_barcode = input("Enter test barcode (or press Enter for default): ").strip()
    if not test_barcode:
        test_barcode = "1234567890123"
    
    # Test communication
    results = pos_comm.test_pos_communication(test_barcode)
    
    print(f"\n🎯 Results for barcode: {test_barcode}")
    for port, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {port}: {status}")
    
    # Test optimized sending
    print(f"\n🚀 Testing optimized sending...")
    success = pos_comm.send_barcode_optimized(test_barcode)
    print(f"Optimized send: {'✅ SUCCESS' if success else '❌ FAILED'}")

if __name__ == "__main__":
    main()
