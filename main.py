# main.py
# SensDot Proto Micropython - ESP32-C3 SuperMini IoT Device
# Entry point for energy-efficient smarthome sensor monitoring
#
# GPIO Configuration:
# TODO: GPIO5 - PIR motion sensor input (configured in pir_wakeup.py)
# TODO: GPIO6 - External LED output (not yet implemented)
# GPIO8 - Internal LED (current status LED with inverted logic)

import sys
import time
import machine
from machine import Pin
from config_manager import ConfigManager
from wifi_config import WiFiConfigServer
from logger import setup_logging, get_logger
from pir_wakeup import check_pir_wake, enable_pir_sleep

# Add lib directory to path for sensor libraries (when needed)
sys.path.append('/lib')
sys.path.append('lib')

# LED setup for status indication
# GPIO pins are now configurable through config_manager
# Default: GPIO8 (internal), GPIO6 (external planned)
try:
    config_manager_temp = ConfigManager()
    gpio_config = config_manager_temp.get_gpio_config()
    status_led = Pin(gpio_config['status_led_pin'], Pin.OUT)
    status_led.on()  # Turn on LED when device starts
    LED_AVAILABLE = True
    LED_PIN = gpio_config['status_led_pin']
    print(f"Status LED initialized on GPIO{LED_PIN}")
except Exception as e:
    LED_AVAILABLE = False
    LED_PIN = None
    print(f"LED not available: {e}")

def led_on():
    """Turn on status LED if available (inverted logic)"""
    if LED_AVAILABLE:
        status_led.off()  # Inverted: off() turns LED ON

def led_off():
    """Turn off status LED if available (inverted logic)"""
    if LED_AVAILABLE:
        status_led.on()  # Inverted: on() turns LED OFF

def led_blink(times=3, delay=0.2, final_on=True):
    """Blink status LED if available (inverted logic)
    final_on: leave LED on at end (default True) else turn it off
    """
    if LED_AVAILABLE:
        for _ in range(times):
            status_led.on()   # Turn LED OFF (inverted)
            time.sleep(delay)
            status_led.off()  # Turn LED ON
            time.sleep(delay)
        if not final_on:
            status_led.on()


def main_cycle(config_manager):
    """Main device cycle - runs after successful configuration"""
    # Setup logging system
    logger = setup_logging(config_manager, console_output=True)
    logger.info("Starting main device cycle...")
    
    # Get configuration
    advanced_config = config_manager.get_advanced_config()
    ntp_config = config_manager.get_ntp_config()
    sleep_interval = advanced_config['sleep_interval']
    sensor_interval = advanced_config['sensor_interval']
    debug_mode = advanced_config['debug_mode']
    
    if debug_mode:
        logger.debug("Debug mode enabled")
        logger.debug(f"Sleep interval: {sleep_interval}s, Sensor interval: {sensor_interval}s")
    else:
        logger.info(f"Sleep interval: {sleep_interval}s, Sensor interval: {sensor_interval}s")
    
    # Bring up WiFi before any network tasks (NTP/MQTT)
    from mqtt_client import SensDotMQTT
    mqtt = SensDotMQTT(config_manager, logger)
    wifi_connected = mqtt.connect_wifi()
    if not wifi_connected:
        logger.error("WiFi not connected; starting AP for reconfiguration")
        wifi_config = WiFiConfigServer(config_manager, logger)
        wifi_config.start_config_server()  # blocks to allow reconfiguration
        return

    # Initialize NTP time synchronization (after WiFi)
    ntp_client = None
    if ntp_config['enable_ntp']:
        if wifi_connected:
            logger.info("Initializing NTP time synchronization...")
            from ntp_client import NTPClient
            dst_region = ntp_config.get('dst_region', 'NONE')
            ntp_client = NTPClient(logger, ntp_config['timezone_offset'], dst_region)
            ntp_client.set_sync_interval(ntp_config['ntp_sync_interval'])
            # Initial time sync
            if ntp_client.sync_time(ntp_config['ntp_server']):
                logger.info("Initial NTP synchronization successful")
            else:
                logger.warn("Initial NTP synchronization failed, will retry later")
        else:
            logger.warn("Skipping initial NTP sync: WiFi not connected")
    else:
        logger.info("NTP synchronization disabled")
    
    # Log system statistics
    log_stats = logger.get_log_stats()
    logger.debug(f"Logging: {log_stats['level']} level, file: {log_stats['log_file']}")
    
    # MQTT setup
    led_blink(2, 0.1)  # Quick blink to indicate MQTT initialization
    
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
        led_blink(1, 0.5)  # Single long blink for successful MQTT connection
        
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
    last_ntp_check = time.time()
    ntp_check_interval = 300  # Check NTP sync every 5 minutes
    
    logger.info("Starting main sensor monitoring cycle...")
    
    # Turn on LED to indicate active monitoring mode
    led_on()
    
    # Check for motion wake notification (only if PIR is enabled and we actually woke from PIR)
    device_id = config_manager.get_device_id()
    pir_config = config_manager.get_pir_config()
    
    # Only check PIR wake if PIR is enabled and deep sleep is being used
    if pir_config.get('enabled', False) and pir_config.get('use_deep_sleep', True):
        was_motion_wake = check_pir_wake()
        if was_motion_wake and mqtt_connected:
            logger.info("Sending motion detection notification...")
            motion_data = {
                "motion_detected": True,
                "wake_time": time.time(),
                "device_id": device_id,
                "event_type": "motion_wake"
            }
            if mqtt.publish_data(motion_data):
                logger.info("Motion notification sent successfully")
            else:
                logger.warning("Failed to send motion notification")
            # Distinct LED pattern for PIR wake: two long pulses
            led_blink(times=2, delay=0.4)
    
    while True:
        try:
            current_time = time.time()
            
            # Keep LED ON while waiting for sensor interval
            led_on()
            
            # Check for incoming MQTT messages (only if connected)
            if mqtt_connected:
                mqtt.check_messages()
            
            # Periodic NTP sync check
            if ntp_client and (current_time - last_ntp_check) >= ntp_check_interval:
                logger.debug("Checking NTP synchronization status...")
                ntp_client.auto_sync_if_needed()
                last_ntp_check = current_time
            
            # Read sensors at specified interval
            if current_time - last_sensor_time >= sensor_interval:
                logger.debug(f"Sensor reading #{sensor_count}")
                led_blink(3, 0.1)  # Triple quick blink for sensor reading
                # LED will be ON after blinking (led_blink ends with LED on)
                
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
                    
                # Check if PIR sleep mode is enabled for power management
                pir_config = config_manager.get_pir_config()
                if pir_config.get('enabled', False) and pir_config.get('use_deep_sleep', True):
                    logger.info(f"Enabling PIR deep sleep mode (sleep={sleep_interval}s, PIR pin={pir_config.get('pir_pin')})...")
                    if mqtt_connected:
                        mqtt.disconnect()  # Clean disconnect
                    # Correct argument order: sleep_seconds first, then config_manager, logger
                    enable_pir_sleep(sleep_interval, config_manager, logger)
                    # Device will wake on motion or timer - this line won't be reached
                    break
                else:
                    # Regular deep sleep mode when PIR disabled
                    logger.info(f"Entering deep sleep for {sleep_interval} seconds...")
                    mqtt.disconnect() if mqtt_connected else None  # Clean disconnect before sleep
                    
                    # LED indication before sleep - turn off LED
                    led_off()
                    time.sleep(0.5)  # Brief pause with LED off to indicate sleep
                    
                    # Enable deep sleep
                    from machine import deepsleep
                    deepsleep(sleep_interval * 1000)  # Convert to milliseconds
                    
                    # This line will never be reached as device restarts after deep sleep
                    
                    # Note: After sleep, continue to next sensor reading
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
        # clear_config is instance method — perform factory reset only when requested
        ConfigManager().clear_config()
    
    # Initialize configuration manager
    config = ConfigManager()
    
    # Setup basic logging (will be enhanced once config is loaded)
    logger = setup_logging(config, console_output=True)
    logger.info("SensDot Proto device starting")
    
    # Check if device is configured first
    if config.is_configured():
        logger.info("Device is configured, checking for PIR wake-up...")

        # Auto-enable PIR deep sleep if disabled (assumes user expects motion wake behavior)
        pir_cfg = config.get_pir_config()
        if not pir_cfg.get('enabled', False):
            logger.info("PIR currently disabled - enabling with defaults (pin=%s)" % pir_cfg.get('pir_pin'))
            config.set_pir_config(pir_enabled=True, pir_pin=pir_cfg.get('pir_pin'),
                                  min_wake_interval=pir_cfg.get('min_wake_interval',300),
                                  motion_timeout=pir_cfg.get('motion_timeout',30),
                                  use_deep_sleep=True)
            pir_cfg = config.get_pir_config()
            logger.info("PIR enabled")

        # Check if device woke from PIR motion - handle early to save power
        if pir_cfg.get('enabled', False):
            logger.info("PIR motion detection enabled, checking wake reason...")
            should_continue = check_pir_wake(config, logger)
            if not should_continue:
                return

        logger.info("Starting main cycle")
        main_cycle(config)
    else:
        logger.info("Device not configured, starting WiFi AP for configuration")
        wifi_config = WiFiConfigServer(config, logger)
        wifi_config.start_config_server()

if __name__ == "__main__":
    main()
