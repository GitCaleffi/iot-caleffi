#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock hardware dependencies
from unittest.mock import MagicMock
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['paho.mqtt.client'] = MagicMock()

# Import and run tests
if __name__ == '__main__':
    import test_barcode_api
    import unittest
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(test_barcode_api)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
