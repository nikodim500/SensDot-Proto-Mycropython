# test_ntp.py
# Test NTP time synchronization functionality

from ntp_client import NTPClient, sync_time_now, get_current_time_formatted
from config_manager import ConfigManager
from logger import setup_logging
import time

def test_ntp_functionality():
    """Test NTP client functionality"""
    print("=== Testing NTP Functionality ===")
    
    # Setup
    config = ConfigManager()
    logger = setup_logging(config, console_output=True)
    
    # Set some NTP configuration for testing
    config.set_ntp_config(
        enable_ntp=True,
        ntp_server="pool.ntp.org",
        timezone_offset=2,  # UTC+2 for testing
        sync_interval=3600
    )
    
    logger.info("Testing NTP time synchronization...")
    
    # Show current time before sync
    logger.info(f"Time before sync: {time.time()}")
    
    # Create NTP client
    ntp_client = NTPClient(logger, timezone_offset=2)
    
    # Test sync status before sync
    status = ntp_client.get_sync_status()
    logger.info(f"Sync status before: {status}")
    
    # Test time synchronization
    logger.info("Attempting NTP synchronization...")
    if ntp_client.sync_time():
        logger.info("NTP synchronization successful!")
        
        # Show updated status
        status = ntp_client.get_sync_status()
        logger.info(f"Sync status after: {status}")
        
        # Test formatted time
        formatted = ntp_client.get_formatted_time()
        logger.info(f"Formatted time: {formatted}")
        
        # Test global functions
        global_formatted = get_current_time_formatted()
        logger.info(f"Global formatted time: {global_formatted}")
        
    else:
        logger.error("NTP synchronization failed")
    
    # Test auto sync check
    logger.info("Testing auto sync check...")
    ntp_client.auto_sync_if_needed()
    
    print("=== NTP Test Completed ===")

def test_ntp_simple():
    """Simple NTP test without full setup"""
    print("=== Simple NTP Test ===")
    
    from logger import get_logger
    logger = get_logger("NTPTest")
    
    # Quick sync test
    if sync_time_now(logger):
        logger.info("Quick NTP sync successful")
        logger.info(f"Current time: {get_current_time_formatted()}")
    else:
        logger.error("Quick NTP sync failed")

if __name__ == "__main__":
    test_ntp_functionality()
    print()
    test_ntp_simple()
