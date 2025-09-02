# pir_wakeup.py
# PIR motion sensor wake-up logic for SensDot device
# Implements intelligent wake-up with configurable minimum intervals

import time
import machine
from machine import Pin, RTC, deepsleep
import json

class PIRWakeup:
    """
    PIR motion sensor wake-up manager
    Handles motion detection with intelligent timing to prevent excessive wake-ups
    """
    
    def __init__(self, pir_pin=None, config_manager=None, logger=None):
        """
        Initialize PIR wake-up system
        
        Args:
            pir_pin: GPIO pin connected to PIR sensor (None to use config_manager)
            config_manager: Configuration manager instance
            logger: Logger instance
        """
        self.config_manager = config_manager
        self.logger = logger
        self.rtc = RTC()
        
        # Get PIR pin from config if not specified
        if pir_pin is None and config_manager:
            gpio_config = config_manager.get_gpio_config()
            self.pir_pin = gpio_config['pir_pin']
        else:
            self.pir_pin = pir_pin or 5  # Default to GPIO5
        
        # Default configuration
        self.min_wake_interval = 300  # 5 minutes minimum between motion alerts
        self.motion_timeout = 30      # 30 seconds to stay awake after motion
        self.load_config()
        
    def load_config(self):
        """Load PIR configuration from config manager"""
        if self.config_manager:
            try:
                pir_config = self.config_manager.get_pir_config()
                self.min_wake_interval = pir_config.get('min_wake_interval', 300)
                self.motion_timeout = pir_config.get('motion_timeout', 30)
                self._log("info", f"PIR config loaded: interval={self.min_wake_interval}s, timeout={self.motion_timeout}s")
            except Exception as e:
                self._log("warn", f"Failed to load PIR config, using defaults: {e}")
    
    def _log(self, level, message):
        """Internal logging helper"""
        if self.logger:
            if level == "debug":
                self.logger.debug(f"PIR: {message}")
            elif level == "info":
                self.logger.info(f"PIR: {message}")
            elif level == "warn":
                self.logger.warn(f"PIR: {message}")
            elif level == "error":
                self.logger.error(f"PIR: {message}")
    
    def get_last_motion_time(self):
        """Get the timestamp of the last motion detection from RTC memory"""
        try:
            # Try to read from RTC memory (persistent across deep sleep)
            rtc_data = self.rtc.memory()
            if len(rtc_data) >= 8:
                # Unpack 8-byte timestamp
                import struct
                last_motion = struct.unpack('<Q', rtc_data[:8])[0]
                return last_motion
        except Exception as e:
            self._log("debug", f"Could not read RTC memory: {e}")
        
        return 0  # No previous motion recorded
    
    def save_motion_time(self, timestamp):
        """Save motion detection timestamp to RTC memory"""
        try:
            import struct
            # Pack timestamp as 8-byte value
            data = struct.pack('<Q', timestamp)
            # Pad to ensure we have enough space
            data += b'\x00' * (32 - len(data))
            self.rtc.memory(data)
            self._log("debug", f"Saved motion time: {timestamp}")
        except Exception as e:
            self._log("warn", f"Failed to save motion time: {e}")
    
    def get_wake_reason(self):
        """Get the reason for waking up from deep sleep"""
        try:
            wake_reason = machine.wake_reason()
            return wake_reason
        except:
            return None
    
    def check_motion_interval(self):
        """
        Check if enough time has passed since last motion detection
        
        Returns:
            tuple: (should_continue, time_since_last)
        """
        current_time = time.time()
        last_motion = self.get_last_motion_time()
        
        if last_motion == 0:
            # No previous motion recorded, proceed
            self._log("info", "First motion detection, proceeding with full boot")
            return True, 0
        
        time_since_last = current_time - last_motion
        
        if time_since_last >= self.min_wake_interval:
            self._log("info", f"Motion detected, {time_since_last}s since last alert (>= {self.min_wake_interval}s), proceeding")
            return True, time_since_last
        else:
            self._log("info", f"Motion detected, but only {time_since_last}s since last alert (< {self.min_wake_interval}s), sleeping")
            return False, time_since_last
    
    def setup_pir_interrupt(self):
        """Setup PIR sensor as wake-up source for deep sleep"""
        try:
            # Configure PIR pin as input with pull-down
            pir = Pin(self.pir_pin, Pin.IN, Pin.PULL_DOWN)
            
            # Configure as wake-up source (rising edge - motion detected)
            machine.Pin.wake_on_level(pir, 1)
            
            self._log("info", f"PIR interrupt configured on GPIO{self.pir_pin}")
            return True
        except Exception as e:
            self._log("error", f"Failed to setup PIR interrupt: {e}")
            return False
    
    def handle_motion_wake(self):
        """
        Handle wake-up from PIR motion detection
        
        Returns:
            bool: True if should continue with full boot, False if should sleep again
        """
        wake_reason = self.get_wake_reason()
        self._log("debug", f"Wake reason: {wake_reason}")
        
        # Check if this was a PIR wake-up
        if wake_reason == machine.PIN_WAKE:
            self._log("info", "Woke up from PIR motion detection")
            
            # Check timing interval
            should_continue, time_since_last = self.check_motion_interval()
            
            if should_continue:
                # Save current motion time
                current_time = time.time()
                self.save_motion_time(current_time)
                self._log("info", "Motion alert approved, continuing with full boot sequence")
                return True
            else:
                # Too soon since last motion, go back to sleep
                remaining_time = self.min_wake_interval - time_since_last
                self._log("info", f"Motion too recent, sleeping for {remaining_time}s more")
                self.go_to_deep_sleep(remaining_time)
                return False  # This line won't be reached due to deep sleep
        else:
            # Not a PIR wake-up (could be timer, reset, etc.)
            self._log("info", "Wake-up not from PIR, proceeding with normal boot")
            return True
    
    def go_to_deep_sleep(self, sleep_seconds=None):
        """
        Put device into deep sleep with PIR wake-up enabled
        
        Args:
            sleep_seconds: Time to sleep in seconds (None for indefinite PIR-only wake)
        """
        # Setup PIR as wake source
        self.setup_pir_interrupt()
        
        if sleep_seconds:
            sleep_ms = int(sleep_seconds * 1000)
            self._log("info", f"Entering deep sleep for {sleep_seconds}s with PIR wake-up")
            deepsleep(sleep_ms)
        else:
            self._log("info", "Entering deep sleep with PIR wake-up only")
            deepsleep()
    
    def send_motion_notification(self, mqtt_client=None):
        """
        Send motion detection notification via MQTT
        
        Args:
            mqtt_client: MQTT client instance
        """
        if not mqtt_client:
            self._log("warn", "No MQTT client provided for motion notification")
            return False
        
        try:
            motion_data = {
                "motion_detected": True,
                "timestamp": time.time(),
                "device_id": self.get_device_id(),
                "wake_reason": "PIR_motion",
                "sensor_type": "motion"
            }
            
            # Publish to motion topic
            topic = f"{mqtt_client.topic_prefix}/motion"
            mqtt_client.publish_data(topic, motion_data)
            
            self._log("info", "Motion notification sent via MQTT")
            return True
        except Exception as e:
            self._log("error", f"Failed to send motion notification: {e}")
            return False
    
    def get_device_id(self):
        """Get unique device ID"""
        try:
            import ubinascii
            device_id = ubinascii.hexlify(machine.unique_id()).decode()
            return device_id
        except:
            return "unknown"
    
    def get_config_dict(self):
        """Get PIR configuration as dictionary for web interface"""
        return {
            "pir_enabled": True,
            "pir_pin": self.pir_pin,
            "min_wake_interval": self.min_wake_interval,
            "motion_timeout": self.motion_timeout
        }


# Convenience functions for main.py integration
def check_pir_wake(config_manager=None, logger=None):
    """
    Check if device woke from PIR and handle accordingly
    
    Returns:
        bool: True if should continue boot, False if went back to sleep
    """
    pir_wake = PIRWakeup(config_manager=config_manager, logger=logger)
    return pir_wake.handle_motion_wake()

def enable_pir_sleep(sleep_seconds=None, config_manager=None, logger=None):
    """
    Enable PIR wake-up and go to deep sleep
    
    Args:
        sleep_seconds: Sleep duration (None for PIR-only wake)
    """
    pir_wake = PIRWakeup(config_manager=config_manager, logger=logger)
    pir_wake.go_to_deep_sleep(sleep_seconds)
