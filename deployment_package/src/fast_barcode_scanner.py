"""
Fast Barcode Scanner - Ultra-optimized for speed with automatic configuration
Eliminates manual setup and provides instant barcode processing
"""
import gradio as gr
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Fast imports - optimized order
from utils.fast_config_manager import get_fast_config_manager, get_config, get_device_status
from utils.fast_api_handler import get_fast_api_handler
from database.local_storage import LocalStorage
from utils.dynamic_device_id import generate_dynamic_device_id

logger = logging.getLogger(__name__)

class FastBarcodeScanner:
    """Ultra-fast barcode scanner with automatic configuration"""
    
    def __init__(self):
        # Initialize fast components
        self.config_manager = get_fast_config_manager()
        self.api_handler = get_fast_api_handler()
        self.local_db = LocalStorage()
        
        # Auto-configuration
        self._auto_configure()
        
        logger.info("🚀 Fast Barcode Scanner initialized")
    
    def _auto_configure(self):
        """Automatic configuration on startup"""
        try:
            config = self.config_manager.get_config()
            
            # Log auto-detection status
            if self.config_manager.is_auto_detected():
                config_path = self.config_manager.get_config_path()
                logger.info(f"✅ Config auto-detected: {config_path}")
            else:
                logger.info("⚡ Using optimized default configuration")
            
            # Auto-detect device status
            device_status = get_device_status()
            logger.info(f"📱 Device connection: {'✅ Online' if device_status else '❌ Offline'}")
            
        except Exception as e:
            logger.warning(f"⚠️ Auto-configuration warning: {e}")
    
    def _setup_ui(self):
        """Setup optimized UI with automatic features"""
        with gr.Blocks(
            title="🚀 Fast Barcode Scanner",
            theme=gr.themes.Soft(),
            css="""
            .fast-scanner { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
            .status-online { color: #10b981; font-weight: bold; }
            .status-offline { color: #ef4444; font-weight: bold; }
            .processing-time { font-size: 0.8em; color: #6b7280; }
            """
        ) as interface:
            
            gr.HTML("""
            <div class="fast-scanner" style="text-align: center; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <h1 style="color: white; margin: 0;">🚀 Fast Barcode Scanner</h1>
                <p style="color: rgba(255,255,255,0.8); margin: 5px 0;">Ultra-fast processing with automatic configuration</p>
            </div>
            """)
            
            with gr.Row():
                with gr.Column(scale=2):
                    # Main scanning interface
                    barcode_input = gr.Textbox(
                        label="📱 Scan or Enter Barcode",
                        placeholder="Scan barcode or type manually...",
                        lines=1,
                        autofocus=True
                    )
                    
                    device_id_input = gr.Textbox(
                        label="🔧 Device ID (Auto-generated if empty)",
                        placeholder="Leave empty for automatic detection",
                        lines=1
                    )
                    
                    with gr.Row():
                        scan_btn = gr.Button("⚡ Fast Scan", variant="primary", scale=2)
                        auto_scan_btn = gr.Button("🔄 Auto Mode", variant="secondary", scale=1)
                
                with gr.Column(scale=1):
                    # System status panel
                    status_display = gr.HTML(self._get_status_html())
                    
                    with gr.Row():
                        refresh_status_btn = gr.Button("🔄 Refresh", size="sm")
                        clear_cache_btn = gr.Button("🗑️ Clear Cache", size="sm")
            
            # Results area
            with gr.Row():
                result_display = gr.JSON(
                    label="📊 Processing Results",
                    show_label=True
                )
            
            # Performance metrics
            with gr.Row():
                performance_display = gr.HTML(
                    """<div style="text-align: center; padding: 10px; background: #f8fafc; border-radius: 5px;">
                    <span class="processing-time">⚡ Ready for ultra-fast processing</span>
                    </div>"""
                )
            
            # Event handlers
            scan_btn.click(
                fn=self._process_barcode_fast,
                inputs=[barcode_input, device_id_input],
                outputs=[result_display, performance_display, status_display]
            )
            
            auto_scan_btn.click(
                fn=self._toggle_auto_mode,
                outputs=[auto_scan_btn]
            )
            
            refresh_status_btn.click(
                fn=self._refresh_status,
                outputs=[status_display]
            )
            
            clear_cache_btn.click(
                fn=self._clear_cache,
                outputs=[performance_display]
            )
            
            # Auto-refresh status every 30 seconds
            interface.load(
                fn=self._auto_refresh_status,
                outputs=[status_display],
                every=30
            )
        
        return interface
    
    async def _process_barcode_fast(self, barcode: str, device_id: str = "") -> tuple:
        """Ultra-fast barcode processing"""
        start_time = time.time()
        
        try:
            # Input validation
            if not barcode or not barcode.strip():
                return (
                    {"error": "❌ Please enter a barcode"},
                    self._get_performance_html(0, "error"),
                    self._get_status_html()
                )
            
            # Auto-generate device ID if empty
            if not device_id.strip():
                device_id = generate_dynamic_device_id()
            
            # Process with fast API handler
            result = await self.api_handler.process_barcode_fast(barcode.strip(), device_id.strip())
            
            processing_time = time.time() - start_time
            
            return (
                result,
                self._get_performance_html(processing_time, "success" if result.get("success") else "error"),
                self._get_status_html()
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Fast processing error: {e}")
            
            return (
                {"error": f"Processing failed: {str(e)}"},
                self._get_performance_html(processing_time, "error"),
                self._get_status_html()
            )
    
    def _toggle_auto_mode(self) -> str:
        """Toggle automatic scanning mode"""
        # Implementation for auto-scanning mode
        return "🔄 Auto Mode (Coming Soon)"
    
    def _refresh_status(self) -> str:
        """Refresh system status"""
        return self._get_status_html()
    
    def _auto_refresh_status(self) -> str:
        """Auto-refresh status for real-time updates"""
        return self._get_status_html()
    
    def _clear_cache(self) -> str:
        """Clear response cache"""
        try:
            # Clear API handler cache
            self.api_handler.response_cache.clear()
            return self._get_performance_html(0, "cache_cleared")
        except Exception as e:
            return f"""<div style="color: #ef4444;">❌ Cache clear failed: {e}</div>"""
    
    def _get_status_html(self) -> str:
        """Generate real-time status HTML"""
        try:
            status = self.api_handler.get_system_status_fast()
            device_connected = status.get("device_connected", False)
            config_auto = status.get("config_auto_detected", False)
            fast_mode = status.get("fast_mode_enabled", True)
            
            status_class = "status-online" if device_connected else "status-offline"
            device_icon = "✅" if device_connected else "❌"
            config_icon = "🎯" if config_auto else "⚙️"
            speed_icon = "⚡" if fast_mode else "🐌"
            
            return f"""
            <div style="padding: 15px; background: #f8fafc; border-radius: 8px; border-left: 4px solid {'#10b981' if device_connected else '#ef4444'};">
                <h4 style="margin: 0 0 10px 0; color: #374151;">📊 System Status</h4>
                
                <div style="margin: 8px 0;">
                    <span class="{status_class}">{device_icon} Device: {'Online' if device_connected else 'Offline'}</span>
                </div>
                
                <div style="margin: 8px 0;">
                    <span style="color: #6b7280;">{config_icon} Config: {'Auto-detected' if config_auto else 'Default'}</span>
                </div>
                
                <div style="margin: 8px 0;">
                    <span style="color: #6b7280;">{speed_icon} Mode: {'Fast' if fast_mode else 'Standard'}</span>
                </div>
                
                <div style="margin: 8px 0; font-size: 0.8em; color: #9ca3af;">
                    Last updated: {datetime.now().strftime('%H:%M:%S')}
                </div>
            </div>
            """
            
        except Exception as e:
            return f"""
            <div style="padding: 15px; background: #fef2f2; border-radius: 8px; border-left: 4px solid #ef4444;">
                <span style="color: #ef4444;">❌ Status Error: {e}</span>
            </div>
            """
    
    def _get_performance_html(self, processing_time: float, status: str) -> str:
        """Generate performance metrics HTML"""
        if status == "cache_cleared":
            return """
            <div style="text-align: center; padding: 10px; background: #f0f9ff; border-radius: 5px;">
                <span style="color: #0ea5e9;">🗑️ Cache cleared successfully</span>
            </div>
            """
        
        time_ms = round(processing_time * 1000, 1)
        
        if status == "error":
            bg_color = "#fef2f2"
            text_color = "#ef4444"
            icon = "❌"
        elif time_ms < 100:
            bg_color = "#f0fdf4"
            text_color = "#16a34a"
            icon = "⚡"
        elif time_ms < 500:
            bg_color = "#fffbeb"
            text_color = "#d97706"
            icon = "🟡"
        else:
            bg_color = "#fef2f2"
            text_color = "#ef4444"
            icon = "🔴"
        
        speed_rating = "Ultra Fast" if time_ms < 100 else "Fast" if time_ms < 500 else "Slow"
        
        return f"""
        <div style="text-align: center; padding: 10px; background: {bg_color}; border-radius: 5px;">
            <span style="color: {text_color};">{icon} {speed_rating}: {time_ms}ms</span>
        </div>
        """
    
    def launch(self, **kwargs):
        """Launch the fast barcode scanner interface"""
        interface = self._setup_ui()
        
        # Default launch settings optimized for speed
        default_kwargs = {
            "server_name": "0.0.0.0",
            "server_port": 7860,
            "share": False,
            "debug": False,
            "show_error": True,
            "quiet": False,
            "inbrowser": True
        }
        
        # Merge with user-provided kwargs
        launch_kwargs = {**default_kwargs, **kwargs}
        
        logger.info(f"🚀 Launching Fast Barcode Scanner on {launch_kwargs['server_name']}:{launch_kwargs['server_port']}")
        
        return interface.launch(**launch_kwargs)

def main():
    """Main entry point for fast barcode scanner"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        scanner = FastBarcodeScanner()
        scanner.launch()
    except KeyboardInterrupt:
        logger.info("👋 Fast Barcode Scanner stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start Fast Barcode Scanner: {e}")

if __name__ == "__main__":
    main()
