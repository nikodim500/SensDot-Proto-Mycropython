# logging_test_device.py
# Simple logging test for ESP32 device
# This script tests the logging system on the actual hardware

from logger import Logger, setup_logging
from config_manager import ConfigManager
import time

def test_logging_on_device():
    """Test logging functionality on ESP32 device"""
    print("=== Testing Logging on ESP32 Device ===")
    
    # Create config manager
    config = ConfigManager()
    
    # Setup logging
    logger = setup_logging(config, console_output=True)
    
    logger.info("Logging system initialized on ESP32")
    logger.debug("This is a debug message")
    logger.warn("This is a warning message")
    logger.error("This is an error message")
    
    # Test logging with device information
    device_id = config.get_device_id()
    logger.info(f"Device ID: {device_id}")
    
    # Test some sensor-like data logging
    for i in range(5):
        logger.info(f"Sensor reading #{i}: temp=25.{i}°C, humidity=60.{i}%")
        time.sleep(1)
    
    # Test exception logging
    try:
        result = 1 / 0
    except:
        logger.exception("Test exception caught")
    
    # Show log statistics
    stats = logger.get_log_stats()
    logger.info(f"Log stats: {stats}")
    
    print("=== Logging test completed ===")
    print("Check for logs/sensdot.log file on device filesystem")

if __name__ == "__main__":
    test_logging_on_device()
