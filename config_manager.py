# config_manager.py
# Configuration management for SensDot Proto device
# Handles persistent storage of WiFi and MQTT settings

import json

class ConfigManager:
    """Manages device configuration storage and retrieval"""
    
    CONFIG_FILE = "device_config.json"
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file"""
        try:
            with open(self.CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (OSError, ValueError):
            # File doesn't exist or is corrupted
            return {}
    
    def _save_config(self):
        """Save configuration to file"""
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.config, f)
            return True
        except OSError:
            print("Error: Could not save configuration")
            return False
    
    def is_configured(self):
        """Check if device has basic configuration"""
        # Only require SSID and MQTT broker - password can be empty for open networks
        return (
            'wifi_ssid' in self.config and self.config['wifi_ssid'] and
            'mqtt_broker' in self.config and self.config['mqtt_broker']
        )
    
    def set_wifi_config(self, ssid, password):
        """Set WiFi configuration"""
        self.config['wifi_ssid'] = ssid
        self.config['wifi_password'] = password
        return self._save_config()
    
    def set_mqtt_config(self, broker, port=1883, username="", password="", topic=""):
        """Set MQTT configuration"""
        self.config['mqtt_broker'] = broker
        self.config['mqtt_port'] = port
        self.config['mqtt_username'] = username
        self.config['mqtt_password'] = password
        self.config['mqtt_topic'] = topic or f"sensdot/{self.get_device_id()}"
        return self._save_config()
    
    def set_device_names(self, device_name="", mqtt_name=""):
        """Set device and MQTT names for identification"""
        # Use defaults if not provided
        default_device_name = f"SensDot-{self.get_device_id()[-4:]}"
        default_mqtt_name = f"sensdot_{self.get_device_id()[-4:]}"
        
        self.config['device_name'] = device_name or default_device_name
        self.config['mqtt_name'] = mqtt_name or default_mqtt_name
        return self._save_config()
    
    def set_advanced_config(self, sleep_interval=60, sensor_interval=30, debug_mode=False, mqtt_discovery=True):
        """Set advanced configuration parameters"""
        self.config['sleep_interval'] = sleep_interval  # Deep sleep duration in seconds
        self.config['sensor_interval'] = sensor_interval  # Sensor reading interval in seconds
        self.config['debug_mode'] = debug_mode  # Enable debug output
        self.config['mqtt_discovery'] = mqtt_discovery  # Enable MQTT Discovery for Home Assistant
        return self._save_config()
    
    def get_wifi_config(self):
        """Get WiFi configuration"""
        return {
            'ssid': self.config.get('wifi_ssid', ''),
            'password': self.config.get('wifi_password', '')
        }
    
    def get_mqtt_config(self):
        """Get MQTT configuration"""
        return {
            'broker': self.config.get('mqtt_broker', ''),
            'port': self.config.get('mqtt_port', 1883),
            'username': self.config.get('mqtt_username', ''),
            'password': self.config.get('mqtt_password', ''),
            'topic': self.config.get('mqtt_topic', f"sensdot/{self.get_device_id()}")
        }
    
    def get_advanced_config(self):
        """Get advanced configuration"""
        return {
            'sleep_interval': self.config.get('sleep_interval', 60),
            'sensor_interval': self.config.get('sensor_interval', 30), 
            'debug_mode': self.config.get('debug_mode', False),
            'mqtt_discovery': self.config.get('mqtt_discovery', True)
        }
    
    def get_device_names(self):
        """Get device and MQTT names"""
        device_id_short = self.get_device_id()[-4:]
        return {
            'device_name': self.config.get('device_name', f"SensDot-{device_id_short}"),
            'mqtt_name': self.config.get('mqtt_name', f"sensdot_{device_id_short}")
        }
    
    def get_device_id(self):
        """Get unique device identifier"""
        import machine
        import ubinascii
        return ubinascii.hexlify(machine.unique_id()).decode()
    
    def clear_config(self):
        """Clear all configuration (factory reset)"""
        self.config = {}
        try:
            import os
            os.remove(self.CONFIG_FILE)
        except OSError:
            pass  # File doesn't exist
    
    def enable_debug_mode(self):
        """Enable debug mode - for developers only, not exposed in web UI"""
        self.config['debug_mode'] = True
        return self._save_config()
    
    def disable_debug_mode(self):
        """Disable debug mode"""
        self.config['debug_mode'] = False
        return self._save_config()
    
    def get_all_config(self):
        """Get all configuration for display/debugging"""
        return self.config.copy()
