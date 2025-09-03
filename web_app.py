#!/usr/bin/env python3
"""
Web app entry point - redirects to the actual barcode scanner application
"""

import sys
import os

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

# Import and run the actual application
if __name__ == "__main__":
    from deployment_package.barcode_scanner_app import main
    main()
