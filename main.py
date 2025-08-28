# main.py
# SensDot Proto Micropython - ESP32-C3 SuperMini IoT Device
# Entry point for energy-efficient smarthome sensor device

import sys
import time
import machine
from config_manager import ConfigManager
from wifi_config import WiFiConfigServer
from logger import setup_logging, get_logger

# Add lib directory to path for sensor libraries (when needed)
sys.path.append('/lib')
sys.path.append('lib')


def main_cycle(config_manager):
    """Main device cycle - runs after successful configuration"""
    # Setup logging system
    logger = setup_logging(config_manager, console_output=True)
    logger.info("Starting main device cycle...")
    
    # Get configuration
    advanced_config = config_manager.get_advanced_config()
    sleep_interval = advanced_config['sleep_interval']
    sensor_interval = advanced_config['sensor_interval']
    debug_mode = advanced_config['debug_mode']
    
    if debug_mode:
        logger.debug("Debug mode enabled")
        logger.debug(f"Sleep interval: {sleep_interval}s, Sensor interval: {sensor_interval}s")
    else:
        logger.info(f"Sleep interval: {sleep_interval}s, Sensor interval: {sensor_interval}s")
    
    # Log system statistics
    log_stats = logger.get_log_stats()
    logger.debug(f"Logging: {log_stats['level']} level, file: {log_stats['log_file']}")
    
    # Initialize MQTT client with retries
    from mqtt_client import SensDotMQTT
    mqtt = SensDotMQTT(config_manager, logger)
    
    # Try to connect to MQTT with retries
    mqtt_retries = 3
    mqtt_connected = False
    
    for attempt in range(mqtt_retries):
        logger.info(f"MQTT connection attempt {attempt + 1}/{mqtt_retries}")
        if mqtt.connect_mqtt():
            mqtt_connected = True
            break
        else:
            logger.warn(f"MQTT connection failed, attempt {attempt + 1}")
            if attempt < mqtt_retries - 1:
                logger.info("Retrying in 5 seconds...")
                time.sleep(5)
    
    if not mqtt_connected:
        logger.error("MQTT connection failed after all retries")
        logger.warn("Device will operate in WiFi-only mode")
        logger.warn("Check MQTT broker settings and restart device")
        # Don't clear config - just operate without MQTT
        # User can reconfigure if needed via reset button
    else:
        logger.info("MQTT connected successfully")
        
        # Publish MQTT Discovery configuration for Home Assistant (if enabled)
        advanced_config = config_manager.get_advanced_config()
        if advanced_config['mqtt_discovery']:
            logger.info("Publishing MQTT Discovery configuration...")
            if mqtt.publish_discovery():
                logger.info("MQTT Discovery published successfully")
            else:
                logger.error("Failed to publish MQTT Discovery")
        else:
            logger.info("MQTT Discovery disabled")
        
        # Publish initial status
        if mqtt.publish_status():
            logger.debug("Initial status published")
        else:
            logger.warn("Failed to publish initial status")
    
    # Main sensor loop
    sensor_count = 0
    last_sensor_time = time.time()
    
    logger.info("Entering main sensor loop")
    
    while True:
        try:
            current_time = time.time()
            
            # Check for incoming MQTT messages (only if connected)
            if mqtt_connected:
                mqtt.check_messages()
            
            # Read sensors at specified interval
            if current_time - last_sensor_time >= sensor_interval:
                logger.debug(f"Sensor reading #{sensor_count}")
                
                # TODO: Read actual sensors here
                # Example sensor data structure for BME280:
                sensor_data = {
                    "temperature": 25.5,  # TODO: Replace with BME280 temperature reading
                    "humidity": 60.2,     # TODO: Replace with BME280 humidity reading  
                    "pressure": 1013.25,  # TODO: Replace with BME280 pressure reading (hPa)
                    "battery": 3.7,       # TODO: Add battery monitoring
                    "iteration": sensor_count,
                    "sleep_interval": sleep_interval
                }
                
                logger.debug(f"Sensor data: {sensor_data}")
                
                # Publish sensor data (only if MQTT connected)
                if mqtt_connected:
                    if mqtt.publish_data(sensor_data):
                        logger.debug("Data published successfully")
                    else:
                        logger.error("Failed to publish data, MQTT disconnected")
                        # Try to reconnect MQTT
                        logger.info("Attempting MQTT reconnection...")
                        if mqtt.connect_mqtt():
                            mqtt_connected = True
                            logger.info("MQTT reconnected")
                        else:
                            mqtt_connected = False
                            logger.error("MQTT reconnection failed")
                else:
                    logger.debug(f"MQTT not connected, data not published")
                
                sensor_count += 1
                last_sensor_time = current_time
                    
                # Deep sleep commented out for testing
                # Enter deep sleep after publishing data
                logger.info(f"Sleeping for {sleep_interval} seconds (using time.sleep for testing)...")
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
            logger.exception(f"Main cycle error: {e}")
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
    
    # Setup basic logging (will be enhanced once config is loaded)
    logger = setup_logging(config, console_output=True)
    logger.info("SensDot Proto device starting")
    
    # Check if device is configured
    if config.is_configured():
        logger.info("Device is configured, starting main cycle")
        main_cycle(config)
    else:
        logger.info("Device not configured, starting WiFi AP for configuration")
        wifi_config = WiFiConfigServer(config, logger)
        wifi_config.start_config_server()

if __name__ == "__main__":
    main()
