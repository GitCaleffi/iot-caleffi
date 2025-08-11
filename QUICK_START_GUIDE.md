# Quick Start Guide for New Users
## Using the Barcode Scanner System (Already Deployed)

The barcode scanner system is already installed and running! Here's how to use it:

## 🌐 **Accessing the System**

### **From the Same Computer (Local Access)**
- Open any web browser (Chrome, Firefox, Safari, etc.)
- Go to: **`http://localhost`**
- You should see the barcode scanner interface

### **From Other Computers on the Same Network**
- Find the server's IP address (ask your IT admin)
- Go to: **`http://[SERVER-IP-ADDRESS]`**
- Example: `http://192.168.1.100`

---

## 🎯 **First Time Setup (One-Time Only)**

### **Step 1: Register Your Device**
1. **Open the web interface** in your browser
2. **Click "Generate Registration Token"** button
3. **Copy the token** that appears (it looks like: `a1b2c3d4e5f6g7h8`)
4. **Enter a Device Name** (example: `warehouse-scanner-01`, `office-scanner`, `john-scanner`)
5. **Click "Confirm Registration"**
6. **Success!** Your device is now registered and ready to use

### **Step 2: Connect Your Barcode Scanner**
1. **Plug your USB barcode scanner** into the computer
2. **Test it** by opening a text editor and scanning - you should see numbers appear
3. **If it doesn't work**: Try a different USB port or restart the scanner

---

## 📱 **Daily Usage**

### **How to Scan Barcodes**
1. **Open the web interface**: `http://localhost`
2. **Make sure your device is registered** (you'll see your device name)
3. **Click in the "Barcode" field** or just scan directly
4. **Scan your barcode** with the USB scanner
5. **The barcode appears automatically** and gets sent to the system
6. **You'll see a success message** confirming it was processed

### **What Happens When You Scan**
- ✅ **Barcode is recorded** in the local database
- ✅ **Data is sent to the cloud** (Azure IoT Hub)
- ✅ **Quantity is updated** in the main system
- ✅ **You can see scan history** on the web interface

---

## 📊 **Viewing Your Data**

### **Check Recent Scans**
- Look at the **"Recent Activity"** section on the main page
- Shows your last scanned barcodes with timestamps

### **View Statistics**
- Go to: `http://localhost/api/stats`
- Shows total scans, success rate, device info

### **Check System Health**
- Go to: `http://localhost/health`
- Shows if everything is working properly

---

## 🔧 **Troubleshooting**

### **Problem: Web page won't load**
**Solutions:**
- Check if the computer is turned on
- Try refreshing the page (F5 or Ctrl+R)
- Try a different web browser
- Contact your IT administrator

### **Problem: Barcode scanner not working**
**Solutions:**
- **Unplug and reconnect** the USB scanner
- **Try a different USB port**
- **Test in a text editor** - scan should type numbers
- **Check if scanner light is on** when you scan

### **Problem: Scans not being saved**
**Solutions:**
- Check if you see **green success messages** after scanning
- Look for **error messages** in red
- Try **refreshing the page** and scanning again
- **Contact IT support** if errors persist

### **Problem: "Device not registered" error**
**Solutions:**
- **Follow the First Time Setup** steps above
- **Generate a new registration token**
- **Make sure you entered a unique device name**

---

## 📋 **Quick Reference**

### **Important URLs** (Bookmark These!)
- **Main Interface**: `http://localhost`
- **System Status**: `http://localhost/health`
- **Statistics**: `http://localhost/api/stats`

### **Common Tasks**
| Task | Steps |
|------|-------|
| **Scan a barcode** | Open web interface → Scan with USB scanner → Check for success message |
| **Register new device** | Generate token → Enter device name → Confirm registration |
| **Check if system is working** | Go to `http://localhost/health` |
| **View scan history** | Look at "Recent Activity" on main page |

### **Who to Contact**
- **Technical Issues**: Your IT Administrator
- **Scanner Hardware Problems**: Check connections first, then contact support
- **Questions about this guide**: Ask your supervisor or IT support

---

## 🎉 **You're Ready to Go!**

The system is already set up and working. Just:
1. **Open your browser** → `http://localhost`
2. **Register your device** (first time only)
3. **Connect USB scanner**
4. **Start scanning barcodes!**

### **Tips for Success**
- ✅ **Keep the web page open** while scanning
- ✅ **Wait for the green success message** after each scan
- ✅ **Don't scan too fast** - give each scan 1-2 seconds
- ✅ **Check the "Recent Activity"** to confirm scans are being recorded

---

## 🆘 **Emergency Help**

If nothing works:

1. **Try restarting your web browser**
2. **Try a different web browser** (Chrome, Firefox, Edge)
3. **Unplug and reconnect your barcode scanner**
4. **Contact your IT administrator** with this information:
   - What you were trying to do
   - What error message you saw (take a screenshot)
   - What web browser you're using

**Remember**: The system is already working - you just need to access it and register your device!
