def check_raspberry_pi_connection(self) -> bool:
        """Check if Raspberry Pi is connected using appropriate method for environment"""
        if self.server_mode:
            return self._check_server_mode_connection()
        return self._check_local_mode_connection()
        
    def _check_server_mode_connection(self) -> bool:
        """Check connection in server mode - prioritize IoT Hub"""
        try:
            # First check IoT Hub connection
            if self.check_iot_hub_connection():
                logger.info("Raspberry Pi connection verified through IoT Hub")
                self.raspberry_pi_devices_available = True
                return True
                
            # Check registered devices in IoT Hub
            config = load_config()
            if config and config.get("iot_hub", {}).get("connection_string"):
                from azure.iot.hub import IoTHubRegistryManager
                try:
                    registry_manager = IoTHubRegistryManager(config["iot_hub"]["connection_string"])
                    # Query for active devices
                    query = "SELECT * FROM devices WHERE status = 'enabled'"
                    devices = registry_manager.query_iot_hub(query)
                    if devices:
                        logger.info(f"Found {len(devices)} active devices in IoT Hub")
                        self.raspberry_pi_devices_available = True
                        return True
                except Exception as e:
                    logger.error(f"IoT Hub registry query failed: {e}")
                    
            logger.warning("No active devices found in IoT Hub")
            self.raspberry_pi_devices_available = False
            return False
            
        except Exception as e:
            logger.error(f"Error checking server mode connection: {e}")
            self.raspberry_pi_devices_available = False
            return False
            
    def _check_local_mode_connection(self) -> bool:
        """Check connection in local mode - use network discovery"""
        try:
            current_time = time.time()
            if current_time - self.last_pi_check >= self.pi_check_interval:
                # Use NetworkDiscovery for local detection
                self.raspberry_pi_devices_available = self.network_discovery.find_raspberry_pi()
                self.last_pi_check = current_time
                
            return self.raspberry_pi_devices_available
            
        except Exception as e:
            logger.error(f"Error checking local mode connection: {e}")
            return False
