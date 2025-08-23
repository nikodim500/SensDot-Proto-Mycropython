# mqtt_client.py
# MQTT client for SensDot device communication

import time
from umqtt.simple import MQTTClient
import network
import json

class SensDotMQTT:
    """MQTT client wrapper for SensDot device"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.client = None
        self.connected = False
        self.wifi = network.WLAN(network.STA_IF)
    
    def connect_wifi(self):
        """Connect to WiFi network"""
        if self.wifi.isconnected():
            print(f"Already connected to WiFi: {self.wifi.ifconfig()[0]}")
            return True
        
        wifi_config = self.config_manager.get_wifi_config()
        ssid = wifi_config['ssid']
        password = wifi_config['password']
        
        if not ssid:
            print("Error: No WiFi SSID configured")
            return False
        
        print(f"Connecting to WiFi: {ssid}")
        self.wifi.active(True)
        self.wifi.connect(ssid, password)
        
        # Wait for connection
        timeout = 10
        while not self.wifi.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
            print(".", end="")
        
        if self.wifi.isconnected():
            print(f"\nWiFi connected: {self.wifi.ifconfig()[0]}")
            return True
        else:
            print("\nWiFi connection failed")
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
            print("Error: No MQTT broker configured")
            return False
        
        # Use custom MQTT name for client ID, with fallback to device ID
        mqtt_name = device_names['mqtt_name']
        if not mqtt_name:
            mqtt_name = f"sensdot_{self.config_manager.get_device_id()[-4:]}"
        
        try:
            print(f"Connecting to MQTT: {broker}:{port} as {mqtt_name}")
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
            print("MQTT connected")
            
            # Subscribe to device command topic using custom MQTT name
            command_topic = f"{mqtt_name}/commands"
            self.client.set_callback(self._message_callback)
            self.client.subscribe(command_topic)
            
            return True
            
        except Exception as e:
            print(f"MQTT connection failed: {e}")
            self.connected = False
            return False
    
    def _message_callback(self, topic, msg):
        """Handle incoming MQTT messages"""
        try:
            topic_str = topic.decode('utf-8')
            msg_str = msg.decode('utf-8')
            print(f"Received message on {topic_str}: {msg_str}")
            
            # Handle basic commands
            if msg_str.lower() == "status":
                self.publish_status()
            elif msg_str.lower() == "restart":
                print("Restart command received")
                import machine
                machine.reset()
            
        except Exception as e:
            print(f"Message handling error: {e}")
    
    def publish_data(self, sensor_data):
        """Publish sensor data to MQTT broker"""
        if not self.connected:
            print("MQTT not connected")
            return False
        
        try:
            mqtt_config = self.config_manager.get_mqtt_config()
            device_names = self.config_manager.get_device_names()
            mqtt_name = device_names['mqtt_name']
            if not mqtt_name:
                mqtt_name = f"sensdot_{self.config_manager.get_device_id()[-4:]}"
                
            topic = f"{mqtt_name}/data"
            
            # Add device metadata with custom names
            payload = {
                "device_id": self.config_manager.get_device_id(),
                "device_name": device_names['device_name'],
                "mqtt_name": mqtt_name,
                "timestamp": time.time(),
                "data": sensor_data
            }
            
            json_payload = json.dumps(payload)
            self.client.publish(topic, json_payload)
            print(f"Published to {topic}: {json_payload}")
            return True
            
        except Exception as e:
            print(f"MQTT publish error: {e}")
            self.connected = False
            return False
    
    def publish_discovery(self):
        """Publish MQTT Discovery configuration for Home Assistant"""
        if not self.connected:
            print("MQTT not connected, cannot publish discovery")
            return False
        
        try:
            device_names = self.config_manager.get_device_names()
            device_id = self.config_manager.get_device_id()
            mqtt_name = device_names['mqtt_name']
            device_name = device_names['device_name']
            
            # Fallback to defaults if not set
            if not mqtt_name:
                mqtt_name = f"sensdot_{device_id[-4:]}"
            if not device_name:
                device_name = f"SensDot-{device_id[-4:]}"
            
            # Base device information for all entities
            device_info = {
                "identifiers": [device_id],
                "name": device_name,
                "model": "SensDot Proto",
                "manufacturer": "SensDot",
                "sw_version": "1.0.0"
            }
            
            print(f"Device info: {device_name} (ID: {device_id})")
            
            # Temperature sensor discovery - use safe approach
            temp_config = {
                "name": "Temperature",
                "unique_id": mqtt_name + "_temperature", 
                "state_topic": mqtt_name + "/data",
                "value_template": "{{ value_json.data.temperature }}",
                "device_class": "temperature",
                "state_class": "measurement"
            }
            
            # Test publish just the temperature sensor first
            topic = "homeassistant/sensor/" + mqtt_name + "_temperature/config"
            
            # Create simple JSON without problematic degree symbol for now
            json_parts = []
            json_parts.append('{"name":"' + temp_config['name'] + '"')
            json_parts.append(',"unique_id":"' + temp_config['unique_id'] + '"') 
            json_parts.append(',"state_topic":"' + temp_config['state_topic'] + '"')
            json_parts.append(',"value_template":"' + temp_config['value_template'] + '"')
            json_parts.append(',"device_class":"' + temp_config['device_class'] + '"')
            json_parts.append(',"state_class":"' + temp_config['state_class'] + '"}')
            
            payload = ''.join(json_parts)
            
            print(f"Testing discovery publish to: {topic}")
            print(f"Simple JSON payload: {payload}")
            print(f"Payload length: {len(payload)} chars")
            
            # Try to publish with error handling
            try:
                self.client.publish(topic, payload, retain=True)
                print("Discovery publish successful")
                
                # Wait a moment to ensure delivery
                import time
                time.sleep(1)
                
                # Check if still connected
                if self.connected:
                    print("MQTT connection stable after discovery publish")
                else:
                    print("MQTT connection lost after discovery publish")
                    
                return True
                
            except Exception as e:
                print(f"Discovery publish failed: {e}")
                self.connected = False
                return False
                
        except Exception as e:
            print(f"Discovery setup error: {e}")
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
