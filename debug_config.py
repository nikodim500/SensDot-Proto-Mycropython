# debug_config.py
# Debug script to check configuration status

from config_manager import ConfigManager
import os

print("=== Configuration Debug ===")

# Check if config file exists
try:
    files = os.listdir()
    print(f"Files on device: {files}")
    if 'device_config.json' in files:
        print("✓ device_config.json exists")
    else:
        print("✗ device_config.json NOT found")
except Exception as e:
    print(f"Error listing files: {e}")

# Try to load config
try:
    config = ConfigManager()
    print(f"✓ ConfigManager loaded successfully")
    
    # Check if configured
    is_configured = config.is_configured()
    print(f"is_configured(): {is_configured}")
    
    # Get all config
    all_config = config.get_all_config()
    print(f"All config: {all_config}")
    
    # Check WiFi config specifically
    wifi_config = config.get_wifi_config()
    print(f"WiFi config: {wifi_config}")
    
    # Check MQTT config
    mqtt_config = config.get_mqtt_config()
    print(f"MQTT config: {mqtt_config}")
    
    # Check required keys individually
    required_keys = ['wifi_ssid', 'wifi_password', 'mqtt_broker']
    for key in required_keys:
        exists = key in config.config
        value = config.config.get(key, 'NOT_SET')
        empty = not bool(value) if exists else True
        print(f"  {key}: exists={exists}, value='{value}', empty={empty}")
    
except Exception as e:
    print(f"✗ Error loading config: {e}")
    import sys
    sys.print_exception(e)

print("=== End Debug ===")
