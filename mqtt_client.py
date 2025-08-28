# mqtt_client.py
# MQTT client for SensDot device communication

import time
try:
    from umqtt.robust import MQTTClient
    print("Loaded umqtt.robust")
except ImportError as e:
    print(f"umqtt.robust not available: {e}")
    try:
        from umqtt.simple import MQTTClient
        print("Loaded umqtt.simple")
    except ImportError as e2:
        print(f"umqtt.simple not available: {e2}")
        print("Error: No MQTT client available")
        raise e2
import network
import json

class SensDotMQTT:
    """MQTT client wrapper for SensDot device"""
    
    def __init__(self, config_manager, logger=None):
        self.config_manager = config_manager
        self.logger = logger
        self.client = None
        self.connected = False
        self.wifi = network.WLAN(network.STA_IF)
    
    def _log(self, level, message):
        """Internal logging method"""
        if self.logger:
            getattr(self.logger, level)(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    def connect_wifi(self):
        """Connect to WiFi network"""
        if self.wifi.isconnected():
            ip = self.wifi.ifconfig()[0]
            self._log("info", f"Already connected to WiFi: {ip}")
            return True
        
        wifi_config = self.config_manager.get_wifi_config()
        ssid = wifi_config['ssid']
        password = wifi_config['password']
        
        if not ssid:
            self._log("error", "No WiFi SSID configured")
            return False
        
        self._log("info", f"Connecting to WiFi: {ssid}")
        self.wifi.active(True)
        self.wifi.connect(ssid, password)
        
        # Wait for connection
        timeout = 10
        while not self.wifi.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print(".", end="")
        
        if self.wifi.isconnected():
            ip = self.wifi.ifconfig()[0]
            self._log("info", f"WiFi connected: {ip}")
            return True
        else:
            self._log("error", "WiFi connection failed")
            return False
    
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        if not self.wifi.isconnected():
            if not self.connect_wifi():
                return False
        
        mqtt_config = self.config_manager.get_mqtt_config()
        device_names = self.config_manager.get_device_names()
        broker = mqtt_config['broker']
        port = mqtt_config['port']
        username = mqtt_config['username']
        password = mqtt_config['password']
        
        if not broker:
            self._log("error", "No MQTT broker configured")
            return False
        
        # Use custom MQTT name for client ID, with fallback to device ID
        mqtt_name = device_names['mqtt_name']
        if not mqtt_name:
            mqtt_name = f"sensdot_{self.config_manager.get_device_id()[-4:]}"
        
        try:
            self._log("info", f"Connecting to MQTT: {broker}:{port} as {mqtt_name}")
            self.client = MQTTClient(
                client_id=mqtt_name,
                server=broker,
                port=port,
                user=username if username else None,
                password=password if password else None,
                keepalive=60
            )
            
            self.client.connect()
            self.connected = True
            self._log("info", "MQTT connected")
            
            # Subscribe to device command topic using custom MQTT name
            command_topic = f"{mqtt_name}/commands"
            self.client.set_callback(self._message_callback)
            self.client.subscribe(command_topic)
            self._log("debug", f"Subscribed to command topic: {command_topic}")
            
            return True
            
        except Exception as e:
            self._log("error", f"MQTT connection failed: {e}")
            self.connected = False
            return False
    
    def _message_callback(self, topic, msg):
        """Handle incoming MQTT messages"""
        try:
            topic_str = topic.decode('utf-8')
            msg_str = msg.decode('utf-8')
            self._log("info", f"Received message on {topic_str}: {msg_str}")
            
            # Handle basic commands
            if msg_str.lower() == "status":
                self._log("debug", "Status command received")
                self.publish_status()
            elif msg_str.lower() == "restart":
                self._log("warn", "Restart command received")
                import machine
                machine.reset()
            elif msg_str.lower() == "clear_logs":
                self._log("info", "Clear logs command received")
                if self.logger:
                    self.logger.clear_logs()
            
        except Exception as e:
            self._log("error", f"Message handling error: {e}")
    
    def publish_data(self, sensor_data):
        """Publish sensor data to MQTT broker"""
        if not self.connected:
            self._log("warn", "MQTT not connected")
            return False
        
        try:
            mqtt_config = self.config_manager.get_mqtt_config()
            device_names = self.config_manager.get_device_names()
            mqtt_name = device_names['mqtt_name']
            if not mqtt_name:
                mqtt_name = f"sensdot_{self.config_manager.get_device_id()[-4:]}"
                
            topic = f"{mqtt_name}/data"
            
            # Get WiFi signal strength for publishing
            wifi_rssi = None
            try:
                if self.wifi.isconnected():
                    wifi_rssi = self.wifi.status('rssi') if hasattr(self.wifi, 'status') else -50
            except:
                wifi_rssi = -50  # Default value
            
            # Create payload compatible with Home Assistant discovery value templates
            payload = {
                "device_id": self.config_manager.get_device_id(),
                "device_name": device_names['device_name'],
                "mqtt_name": mqtt_name,
                "timestamp": time.time(),
                "wifi_rssi": wifi_rssi,
                "data": sensor_data
            }
            
            json_payload = json.dumps(payload)
            self.client.publish(topic, json_payload)
            self._log("debug", f"Published to {topic}: {len(json_payload)} bytes")
            return True
            
        except Exception as e:
            self._log("error", f"MQTT publish error: {e}")
            self.connected = False
            return False
    
    def publish_discovery(self):
        """Publish MQTT Discovery configuration for Home Assistant"""
        if not self.connected:
            print("MQTT not connected, cannot publish discovery")
            return False
        
        try:
            import ubinascii
            import machine
            
            device_names = self.config_manager.get_device_names()
            device_id = self.config_manager.get_device_id()
            mqtt_name = device_names['mqtt_name']
            device_name = device_names['device_name']
            
            # Fallback to defaults if not set
            if not mqtt_name:
                mqtt_name = f"sensdot_{device_id[-4:]}"
            if not device_name:
                device_name = f"SensDot-{device_id[-4:]}"
            
            print(f"Publishing discovery for: {device_name} (MQTT: {mqtt_name})")
            
            # Get unique hardware ID for identifiers
            unique_id = ubinascii.hexlify(machine.unique_id()).decode()
            
            # Single device information for ALL entities - this groups them together
            device_info = {
                "identifiers": [mqtt_name],  # Use mqtt_name as device identifier
                "name": device_name,
                "model": "ESP32-C3 SuperMini", 
                "manufacturer": "SensDot",
                "sw_version": "1.0.0"
            }
            
            # Temperature sensor discovery
            temp_topic = "homeassistant/sensor/" + mqtt_name + "_temperature/config"
            
            try:
                # Method 1: Use \\u00B0 Unicode escape for degree symbol
                temp_json = '{"name":"' + device_name + ' Temperature",'
                temp_json += '"unique_id":"' + mqtt_name + '_temperature",'
                temp_json += '"device_class":"temperature",'
                temp_json += '"unit_of_measurement":"\\u00B0C",'  # Unicode escape for °C
                temp_json += '"state_class":"measurement",'
                temp_json += '"state_topic":"' + mqtt_name + '/data",'
                temp_json += '"value_template":"{{ value_json.data.temperature }}",'
                temp_json += '"device":{"identifiers":["' + mqtt_name + '"],'
                temp_json += '"name":"' + device_name + '",'
                temp_json += '"model":"ESP32-C3 SuperMini",'
                temp_json += '"manufacturer":"SensDot",'
                temp_json += '"sw_version":"1.0.0"}}'
                
                print(f"Unicode JSON length: {len(temp_json)} chars")
                print(f"Unicode JSON: {temp_json}")
                
                # Publish with retain=True
                self.client.publish(temp_topic, temp_json, retain=True)
                print(f"Published temperature discovery: {temp_topic}")
            except Exception as e:
                print(f"Error publishing temperature discovery: {e}")
                
                # Method 2: Fallback to bytes encoding if unicode fails
                try:
                    print("Trying bytes encoding fallback...")
                    temp_json_bytes = b'{"name":"' + device_name.encode('utf-8') + b' Temperature",'
                    temp_json_bytes += b'"unique_id":"' + mqtt_name.encode('utf-8') + b'_temperature",'
                    temp_json_bytes += b'"device_class":"temperature",'
                    temp_json_bytes += b'"unit_of_measurement":"\xc2\xb0C",'  # UTF-8 bytes for °C
                    temp_json_bytes += b'"state_class":"measurement",'
                    temp_json_bytes += b'"state_topic":"' + mqtt_name.encode('utf-8') + b'/data",'
                    temp_json_bytes += b'"value_template":"{{ value_json.data.temperature }}",'
                    temp_json_bytes += b'"device":{"identifiers":["' + mqtt_name.encode('utf-8') + b'"],'
                    temp_json_bytes += b'"name":"' + device_name.encode('utf-8') + b'",'
                    temp_json_bytes += b'"model":"ESP32-C3 SuperMini",'
                    temp_json_bytes += b'"manufacturer":"SensDot",'
                    temp_json_bytes += b'"sw_version":"1.0.0"}}'
                    
                    print(f"Bytes JSON length: {len(temp_json_bytes)} bytes")
                    
                    # Publish bytes directly
                    self.client.publish(temp_topic, temp_json_bytes, retain=True)
                    print(f"Published temperature discovery with bytes: {temp_topic}")
                except Exception as e2:
                    print(f"Bytes encoding also failed: {e2}")
                    
                    # Method 3: Final fallback to simple "C" unit
                    try:
                        print("Final fallback to simple C unit...")
                        temp_json_simple = '{"name":"' + device_name + ' Temperature",'
                        temp_json_simple += '"unique_id":"' + mqtt_name + '_temperature",'
                        temp_json_simple += '"device_class":"temperature",'
                        temp_json_simple += '"unit_of_measurement":"C",'  # Simple C without degree
                        temp_json_simple += '"state_class":"measurement",'
                        temp_json_simple += '"state_topic":"' + mqtt_name + '/data",'
                        temp_json_simple += '"value_template":"{{ value_json.data.temperature }}",'
                        temp_json_simple += '"device":{"identifiers":["' + mqtt_name + '"],'
                        temp_json_simple += '"name":"' + device_name + '",'
                        temp_json_simple += '"model":"ESP32-C3 SuperMini",'
                        temp_json_simple += '"manufacturer":"SensDot",'
                        temp_json_simple += '"sw_version":"1.0.0"}}'
                        
                        self.client.publish(temp_topic, temp_json_simple, retain=True)
                        print(f"Published temperature discovery with simple C: {temp_topic}")
                    except Exception as e3:
                        print(f"All methods failed: {e3}")
            
            # Wait briefly between messages
            time.sleep(2.0)
            
            # Humidity sensor discovery
            humidity_topic = "homeassistant/sensor/" + mqtt_name + "_humidity/config"
            
            try:
                humidity_json = '{"name":"' + device_name + ' Humidity",'
                humidity_json += '"unique_id":"' + mqtt_name + '_humidity",'
                humidity_json += '"device_class":"humidity",'
                humidity_json += '"unit_of_measurement":"%",'
                humidity_json += '"state_class":"measurement",'
                humidity_json += '"state_topic":"' + mqtt_name + '/data",'
                humidity_json += '"value_template":"{{ value_json.data.humidity }}",'
                humidity_json += '"device":{"identifiers":["' + mqtt_name + '"],'
                humidity_json += '"name":"' + device_name + '",'
                humidity_json += '"model":"ESP32-C3 SuperMini",'
                humidity_json += '"manufacturer":"SensDot",'
                humidity_json += '"sw_version":"1.0.0"}}'
                
                print(f"Humidity JSON length: {len(humidity_json)} chars")
                
                self.client.publish(humidity_topic, humidity_json, retain=True)
                print(f"Published humidity discovery: {humidity_topic}")
            except Exception as e:
                print(f"Error publishing humidity discovery: {e}")
            
            print("MQTT Discovery published successfully (temperature and humidity only)")
            return True
            
        except Exception as e:
            print(f"Discovery publish error: {e}")
            import sys
            sys.print_exception(e)
            return False
    
    def publish_status(self):
        """Publish device status"""
        if not self.connected:
            return False
        
        try:
            mqtt_config = self.config_manager.get_mqtt_config()
            device_names = self.config_manager.get_device_names()
            mqtt_name = device_names['mqtt_name']
            if not mqtt_name:
                mqtt_name = f"sensdot_{self.config_manager.get_device_id()[-4:]}"
                
            topic = f"{mqtt_name}/status"
            
            # Get WiFi signal strength
            wifi_rssi = None
            try:
                import network
                sta = network.WLAN(network.STA_IF)
                if sta.isconnected():
                    # Get signal strength (implementation varies by platform)
                    wifi_rssi = sta.status('rssi') if hasattr(sta, 'status') else None
            except:
                pass
            
            status = {
                "device_id": self.config_manager.get_device_id(),
                "device_name": device_names['device_name'],
                "mqtt_name": mqtt_name,
                "timestamp": time.time(),
                "wifi_ip": self.wifi.ifconfig()[0] if self.wifi.isconnected() else None,
                "wifi_rssi": wifi_rssi,
                "free_memory": self._get_free_memory(),
                "uptime": time.ticks_ms() // 1000
            }
            
            json_payload = json.dumps(status)
            self.client.publish(topic, json_payload, retain=True)
            print(f"Status published: {json_payload}")
            return True
            
        except OSError as e:
            if e.args[0] == 104:  # ECONNRESET
                print("MQTT disconnected during status publish")
                self.connected = False
                return False
            else:
                print(f"Status publish error: {e}")
                return False
        except Exception as e:
            print(f"Status publish error: {e}")
            self.connected = False
            return False
    
    def _get_free_memory(self):
        """Get free memory in bytes"""
        try:
            import gc
            gc.collect()
            return gc.mem_free()
        except:
            return -1
    
    def check_messages(self):
        """Check for incoming MQTT messages"""
        if self.connected and self.client:
            try:
                self.client.check_msg()
            except OSError as e:
                if e.args[0] == 104:  # ECONNRESET
                    print("MQTT disconnected, reconnecting...")
                    self.connected = False
                    # Try to reconnect
                    if self.connect_mqtt():
                        print("MQTT reconnected")
                    else:
                        print("MQTT reconnection failed")
                else:
                    print(f"MQTT error: {e}")
                    self.connected = False
            except Exception as e:
                print(f"MQTT error: {e}")
                self.connected = False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            try:
                self.client.disconnect()
                print("MQTT disconnected")
            except:
                pass
        self.connected = False
    
    def is_connected(self):
        """Check if MQTT is connected"""
        return self.connected
