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
        broker = mqtt_config['broker']
        port = mqtt_config['port']
        username = mqtt_config['username']
        password = mqtt_config['password']
        
        if not broker:
            print("Error: No MQTT broker configured")
            return False
        
        client_id = f"sensdot_{self.config_manager.get_device_id()}"
        
        try:
            print(f"Connecting to MQTT broker: {broker}:{port}")
            self.client = MQTTClient(
                client_id=client_id,
                server=broker,
                port=port,
                user=username if username else None,
                password=password if password else None,
                keepalive=60
            )
            
            self.client.connect()
            self.connected = True
            print("MQTT connected successfully")
            
            # Subscribe to device command topic
            command_topic = f"{mqtt_config['topic']}/commands"
            self.client.set_callback(self._message_callback)
            self.client.subscribe(command_topic)
            print(f"Subscribed to: {command_topic}")
            
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
            topic = f"{mqtt_config['topic']}/data"
            
            # Add device metadata
            payload = {
                "device_id": self.config_manager.get_device_id(),
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
    
    def publish_status(self):
        """Publish device status"""
        if not self.connected:
            return False
        
        try:
            mqtt_config = self.config_manager.get_mqtt_config()
            topic = f"{mqtt_config['topic']}/status"
            
            status = {
                "device_id": self.config_manager.get_device_id(),
                "timestamp": time.time(),
                "wifi_ip": self.wifi.ifconfig()[0] if self.wifi.isconnected() else None,
                "free_memory": self._get_free_memory(),
                "uptime": time.ticks_ms() // 1000
            }
            
            json_payload = json.dumps(status)
            self.client.publish(topic, json_payload, retain=True)
            print(f"Status published: {json_payload}")
            return True
            
        except Exception as e:
            print(f"Status publish error: {e}")
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
            except Exception as e:
                print(f"MQTT check messages error: {e}")
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
