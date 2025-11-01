# main.py
# SensDot Proto Micropython - ESP32-C3 SuperMini IoT Device
# Entry point for energy-efficient smarthome sensor monitoring
#
# GPIO Configuration:
# TODO: GPIO5 - PIR motion sensor input (configured in pir_wakeup.py)
# External LED: default GPIO10 (configurable). Safe as general-purpose output on ESP32-C3.
# GPIO8 - Internal LED (current status LED with inverted logic)

import sys
import time
import machine
from machine import Pin
from config_manager import ConfigManager
from wifi_config import WiFiConfigServer
from logger import setup_logging, get_logger
from pir_wakeup import check_pir_wake, enable_pir_sleep
from indication import IndicationManager

# Add lib directory to path for sensor libraries (when needed)
sys.path.append('/lib')
sys.path.append('lib')

# All LED handling moved to indication.py

def _prepare_pir_irq_for_lightsleep(pir_pin, logger=None):
    """Configure PIR pin IRQ so it can wake from light sleep.
    On ESP32-C3, Pin.irq can be used to wake from lightsleep.
    """
    try:
        pir = Pin(pir_pin, Pin.IN)
        # Dummy handler; presence of IRQ enables wake from lightsleep
        pir.irq(trigger=Pin.IRQ_RISING, handler=lambda p: None)
        if logger:
            logger.debug(f"Configured PIR GPIO{pir_pin} IRQ for light sleep wake")
        return True
    except Exception as e:
        if logger:
            logger.warn(f"Failed to configure PIR IRQ for light sleep: {e}")
        return False


def main_cycle(config_manager, indicator):
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
    indicator.blink(2, 0.1)  # Quick blink to indicate MQTT initialization
    
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
        indicator.blink(1, 0.5)  # Single long blink for successful MQTT connection
        
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
    indicator.on()
    
    # Check for motion wake notification (only if PIR is enabled and we actually woke from PIR)
    device_id = config_manager.get_device_id()
    pir_config = config_manager.get_pir_config()
    
    # Only check PIR wake if PIR is enabled and deep sleep is being used
    if pir_config.get('enabled', False) and pir_config.get('use_deep_sleep', True):
        was_motion_wake = check_pir_wake(config_manager, logger)
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
            indicator.blink(times=2, delay=0.4)
    
    while True:
        try:
            current_time = time.time()
            
            # Keep LED ON while waiting for sensor interval
            indicator.on()
            
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
                indicator.blink(3, 0.1)  # Triple quick blink for sensor reading
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
                    
                # Choose sleep mode based on configuration
                pir_config = config_manager.get_pir_config()
                use_deep = pir_config.get('use_deep_sleep', True)

                if use_deep:
                    # Deep sleep path (default). If PIR enabled, configure PIR wake; otherwise timer only.
                    if mqtt_connected:
                        mqtt.disconnect()  # Clean disconnect

                    # LED indication before sleep - turn off LED
                    indicator.off()
                    time.sleep(0.5)

                    if pir_config.get('enabled', False):
                        logger.info(f"Deep sleep with PIR wake (sleep={sleep_interval}s, PIR pin={pir_config.get('pir_pin')})")
                        enable_pir_sleep(sleep_interval, config_manager, logger)
                        break  # Not reached due to deep sleep
                    else:
                        logger.info(f"Entering deep sleep for {sleep_interval} seconds (timer only)...")
                        from machine import deepsleep
                        deepsleep(int(sleep_interval * 1000))
                        break  # Not reached due to deep sleep
                else:
                    # Light sleep path (explicitly configured). Optionally wake by PIR IRQ.
                    logger.info(f"Entering light sleep for {sleep_interval} seconds...")
                    mqtt.disconnect() if mqtt_connected else None  # Clean disconnect before sleep

                    # LED indication before sleep - turn off LED
                    indicator.off()
                    time.sleep(0.2)

                    # Prepare PIR IRQ (if PIR enabled) to allow wake on motion
                    if pir_config.get('enabled', False):
                        _prepare_pir_irq_for_lightsleep(pir_config.get('pir_pin'), logger)

                    try:
                        import machine
                        # Use regular sleep to keep REPL responsive instead of lightsleep
                        import time as _t
                        _t.sleep(int(sleep_interval))
                    except Exception as _se:
                        logger.warn(f"lightsleep failed ({_se}); falling back to time.sleep")
                        time.sleep(sleep_interval)
                    # Execution resumes here after lightsleep timeout or PIR IRQ
                    indicator.on()
            else:
                # Wait a bit before next check
                time.sleep(1)
                
        except Exception as e:
            logger.exception(f"Main cycle error: {e}")
            time.sleep(5)  # Wait before retrying

def check_config_reset(logger=None):
    """Check if configuration should be reset via button press"""
    from machine import Pin
    
    # GPIO pin for reset button (adjust as needed for your hardware)
    # Using GPIO9 (available on ESP32-C3 SuperMini)
    reset_button = Pin(9, Pin.IN, Pin.PULL_UP)
    
    # Check if button is pressed (LOW when pressed due to pull-up)
    if not reset_button.value():
        if logger:
            logger.info("Reset button pressed, checking for hold...")
        else:
            print("Reset button pressed, checking for hold...")
        
        # Require button hold for 3 seconds to prevent accidental reset
        import time
        hold_time = 0
        while not reset_button.value() and hold_time < 3:
            time.sleep(0.1)
            hold_time += 0.1
        
        if hold_time >= 2.9:  # Allow small tolerance
            if logger:
                logger.info("Reset button held for 3 seconds - configuration will be reset")
            else:
                print("Reset button held for 3 seconds - configuration will be reset")
            return True
        else:
            if logger:
                logger.info("Reset button not held long enough")
            else:
                print("Reset button not held long enough")
    
    return False

def main():
    """Device entry point"""
    # Initialize configuration manager and logging first for consistent timestamps
    config = ConfigManager()
    logger = setup_logging(config, console_output=True)
    logger.info("SensDot Proto starting...")
    # Prepare indicator early
    indicator = IndicationManager(config, logger)
    indicator.setup()
    # Optional halt mechanism: if a flag file exists, do not start main cycle
    try:
        import os
        if 'halt.flag' in os.listdir():
            try:
                indicator.ensure_external_safe_off()
            except Exception:
                pass
            try:
                logger.warn("HALT flag present - skipping main cycle and staying in REPL")
            except:
                pass
            return
    except Exception as _fe:
        try:
            logger.debug("Halt flag check failed: {}".format(_fe))
        except:
            pass
    # Log external LED flag for visibility
    try:
        gpio_cfg = config.get_gpio_config()
        logger.info("External LED flag: {} (pin={})".format(
            'ENABLED' if gpio_cfg.get('external_led_enabled', True) else 'DISABLED',
            gpio_cfg.get('external_led_pin', 'n/a')
        ))
    except Exception as _elog:
        try:
            logger.warn("External LED flag log failed: {}".format(_elog))
        except:
            pass
    
    # Check for configuration reset request
    if check_config_reset(logger):
        logger.info("Configuration reset requested")
        # clear_config is instance method — perform factory reset only when requested
        config.clear_config()
        # Re-initialize logger after reset in case settings changed
        config = ConfigManager()
        logger = setup_logging(config, console_output=True)
        logger.info("Configuration cleared; continuing with AP setup if needed")

    # Check if device is configured
    if config.is_configured():
        logger.info("Device is configured, checking for PIR wake-up...")

        # Auto-enable PIR with light sleep by default if disabled
        pir_cfg = config.get_pir_config()
        if not pir_cfg.get('enabled', False):
            logger.info("PIR currently disabled - enabling with light sleep defaults (pin=%s)" % pir_cfg.get('pir_pin'))
            config.set_pir_config(pir_enabled=True, pir_pin=pir_cfg.get('pir_pin'),
                                  min_wake_interval=pir_cfg.get('min_wake_interval',300),
                                  motion_timeout=pir_cfg.get('motion_timeout',30),
                                  use_deep_sleep=False)
            pir_cfg = config.get_pir_config()
            logger.info("PIR enabled (light sleep mode)")

        # Check if device woke from PIR motion - only for deep sleep mode
        if pir_cfg.get('enabled', False) and pir_cfg.get('use_deep_sleep', True):
            logger.info("PIR motion detection enabled, checking wake reason...")
            should_continue = check_pir_wake(config, logger)
            if not should_continue:
                return

        logger.info("Starting main cycle")
        main_cycle(config, indicator)
    else:
        logger.info("Device not configured, starting WiFi AP for configuration")
        wifi_config = WiFiConfigServer(config, logger)
        wifi_config.start_config_server()

if __name__ == "__main__":
    main()
