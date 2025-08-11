# 📱 BARCODE SCANNER SYSTEM - QUICK REFERENCE CARD
**Print this card and keep it at your workstation!**

---

## 🌐 **ACCESS THE SYSTEM**
**Web Address:** `http://localhost`  
**From other computers:** `http://[ask-IT-for-IP-address]`

---

## 🎯 **FIRST TIME SETUP** (One-time only)
1. **Open web browser** → Go to `http://localhost`
2. **Click "Generate Registration Token"**
3. **Enter your device name** (example: `john-scanner`)
4. **Click "Confirm Registration"**
5. **Done!** Your scanner is ready to use

---

## 📱 **DAILY SCANNING**
1. **Open web browser** → `http://localhost`
2. **Connect USB barcode scanner**
3. **Scan barcodes** - they appear automatically
4. **Look for GREEN success messages**
5. **Check "Recent Activity" to see your scans**

---

## ✅ **SUCCESS INDICATORS**
- ✅ **Green message** appears after scanning
- ✅ **Barcode appears in "Recent Activity"**
- ✅ **Numbers increase in statistics**

---

## ❌ **TROUBLESHOOTING**
| Problem | Solution |
|---------|----------|
| **Web page won't load** | Refresh page (F5) or try different browser |
| **Scanner not working** | Unplug/reconnect USB scanner |
| **No success message** | Wait 2 seconds between scans |
| **"Device not registered"** | Do First Time Setup again |

---

## 📞 **NEED HELP?**
1. **Try the solutions above first**
2. **Take a screenshot of any error messages**
3. **Contact your IT Administrator**
4. **Tell them exactly what you were doing when the problem occurred**

---

## 🔗 **USEFUL LINKS**
- **Main Interface:** `http://localhost`
- **Check System Status:** `http://localhost/health`
- **View Statistics:** `http://localhost/api/stats`

---

**💡 TIP:** Keep this web page bookmarked in your browser for easy access!

---

```
┌─────────────────────────────────────────────┐
│        EMERGENCY RESTART STEPS              │
├─────────────────────────────────────────────┤
│ 1. Close web browser completely             │
│ 2. Unplug USB scanner                       │
│ 3. Wait 10 seconds                          │
│ 4. Plug USB scanner back in                 │
│ 5. Open browser → http://localhost          │
│ 6. Try scanning again                       │
└─────────────────────────────────────────────┘
```

**System Status Check:** If you see `{"status": "healthy"}` at `http://localhost/health`, everything is working!
