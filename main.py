# main.py
# SensDot Proto Micropython - ESP32-C3 SuperMini IoT Device
# Entry point for energy-efficient smarthome sensor device

import sys
import time
import machine
from config_manager import ConfigManager
from wifi_config import WiFiConfigServer

# Add lib directory to path for sensor libraries (when needed)
sys.path.append('/lib')
sys.path.append('lib')


def main_cycle(config_manager):
    """Main device cycle - runs after successful configuration"""
    print("Starting main device cycle...")
    
    # Get configuration
    advanced_config = config_manager.get_advanced_config()
    sleep_interval = advanced_config['sleep_interval']
    sensor_interval = advanced_config['sensor_interval']
    debug_mode = advanced_config['debug_mode']
    
    if debug_mode:
        print(f"Debug mode enabled")
        print(f"Sleep interval: {sleep_interval}s, Sensor interval: {sensor_interval}s")
    
    # Initialize MQTT client with retries
    from mqtt_client import SensDotMQTT
    mqtt = SensDotMQTT(config_manager)
    
    # Try to connect to MQTT with retries
    mqtt_retries = 3
    mqtt_connected = False
    
    for attempt in range(mqtt_retries):
        print(f"MQTT connection attempt {attempt + 1}/{mqtt_retries}")
        if mqtt.connect_mqtt():
            mqtt_connected = True
            break
        else:
            print(f"MQTT connection failed, attempt {attempt + 1}")
            if attempt < mqtt_retries - 1:
                print("Retrying in 5 seconds...")
                time.sleep(5)
    
    if not mqtt_connected:
        print("MQTT connection failed after all retries")
        print("Device will operate in WiFi-only mode")
        print("Check MQTT broker settings and restart device")
        # Don't clear config - just operate without MQTT
        # User can reconfigure if needed via reset button
    else:
        print("MQTT connected successfully")
        
        # Publish MQTT Discovery configuration for Home Assistant (if enabled)
        advanced_config = config_manager.get_advanced_config()
        if advanced_config['mqtt_discovery']:
            print("Publishing MQTT Discovery configuration...")
            mqtt.publish_discovery()
        else:
            print("MQTT Discovery disabled")
        
        # Publish initial status
        mqtt.publish_status()
    
    # Main sensor loop
    sensor_count = 0
    last_sensor_time = time.time()
    
    while True:
        try:
            current_time = time.time()
            
            # Check for incoming MQTT messages (only if connected)
            if mqtt_connected:
                mqtt.check_messages()
            
            # Read sensors at specified interval
            if current_time - last_sensor_time >= sensor_interval:
                if debug_mode:
                    print(f"Sensor reading #{sensor_count}")
                
                # TODO: Read actual sensors here
                # Example sensor data structure:
                sensor_data = {
                    "temperature": 25.5,  # TODO: Replace with actual sensor reading
                    "humidity": 60.2,     # TODO: Replace with actual sensor reading
                    "battery": 3.7,       # TODO: Add battery monitoring
                    "iteration": sensor_count,
                    "sleep_interval": sleep_interval
                }
                
                # Publish sensor data (only if MQTT connected)
                if mqtt_connected:
                    if mqtt.publish_data(sensor_data):
                        if debug_mode:
                            print(f"Data published successfully")
                    else:
                        print("Failed to publish data, MQTT disconnected")
                        # Try to reconnect MQTT
                        if mqtt.connect_mqtt():
                            mqtt_connected = True
                            print("MQTT reconnected")
                        else:
                            mqtt_connected = False
                else:
                    if debug_mode:
                        print(f"MQTT not connected, data not published: {sensor_data}")
                
                sensor_count += 1
                last_sensor_time = current_time
                    
                # Deep sleep commented out for testing
                # Enter deep sleep after publishing data
                print(f"Sleeping for {sleep_interval} seconds (using time.sleep for testing)...")
                # mqtt.disconnect()  # Clean disconnect before sleep
                
                # Deep sleep - COMMENTED OUT FOR TESTING
                # from machine import deepsleep
                # deepsleep(sleep_interval * 1000)  # Convert to milliseconds
                
                # Using regular sleep for testing instead of deep sleep
                time.sleep(sleep_interval)
                
                # Note: With deep sleep disabled, we continue the loop
                # In production, deep sleep would restart the device
            else:
                # Wait a bit before next check
                time.sleep(1)
                
        except Exception as e:
            print(f"Main cycle error: {e}")
            if debug_mode:
                import sys
                sys.print_exception(e)
            time.sleep(5)  # Wait before retrying

def check_config_reset():
    """Check if configuration should be reset via button press"""
    from machine import Pin
    
    # GPIO pin for reset button (adjust as needed for your hardware)
    # Using GPIO9 (available on ESP32-C3 SuperMini)
    reset_button = Pin(9, Pin.IN, Pin.PULL_UP)
    
    # Check if button is pressed (LOW when pressed due to pull-up)
    if not reset_button.value():
        print("Reset button pressed, checking for hold...")
        
        # Require button hold for 3 seconds to prevent accidental reset
        import time
        hold_time = 0
        while not reset_button.value() and hold_time < 3:
            time.sleep(0.1)
            hold_time += 0.1
        
        if hold_time >= 2.9:  # Allow small tolerance
            print("Reset button held for 3 seconds - configuration will be reset")
            return True
        else:
            print("Reset button not held long enough")
    
    return False

def main():
    """Device entry point"""
    print("SensDot Proto starting...")
    
    # Check for configuration reset request
    if check_config_reset():
        print("Configuration reset requested")
        ConfigManager.clear_config()
    
    # Initialize configuration manager
    config = ConfigManager()
    
    # Check if device is configured
    if config.is_configured():
        print("Device is configured, starting main cycle")
        main_cycle(config)
    else:
        print("Device not configured, starting WiFi AP for configuration")
        wifi_config = WiFiConfigServer(config)
        wifi_config.start_config_server()

if __name__ == "__main__":
    main()
