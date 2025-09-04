#!/usr/bin/env python3

from flask import Flask, jsonify
import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <h1>Barcode Scanner Test</h1>
    <p><a href="/test-registration">Test Device Registration</a></p>
    <p><a href="/test-scan">Test Barcode Scan</a></p>
    <p><a href="/status">Check Device Status</a></p>
    '''

@app.route('/test-registration')
def test_registration():
    try:
        from test_api_functions import load_or_register
        result = load_or_register()
        return f"<h2>Registration Test</h2><pre>{result}</pre>"
    except Exception as e:
        return f"<h2>Registration Failed</h2><p>{str(e)}</p>"

@app.route('/test-scan')
def test_scan():
    return '''
    <h2>Scan Test</h2>
    <p>Device: pi-test123</p>
    <p>Barcode: 1234567890123</p>
    <p>Status: Scan sent to MQTT</p>
    '''

@app.route('/status')
def status():
    try:
        from test_api_functions import ethernet_connected, internet_ok, get_ip
        return jsonify({
            "ethernet": ethernet_connected(),
            "internet": internet_ok(), 
            "ip": get_ip()
        })
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5555, debug=True)
