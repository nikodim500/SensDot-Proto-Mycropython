# test_exception_logging.py
# Test exception logging specifically

from logger import setup_logging
from config_manager import ConfigManager

def test_exception():
    """Test exception logging"""
    print("Testing exception logging...")
    
    config = ConfigManager()
    logger = setup_logging(config, console_output=True)
    
    # Test normal exception logging
    try:
        result = 1 / 0
    except:
        logger.exception("Division by zero test")
    
    # Test exception logging with custom message
    try:
        x = {}
        y = x['nonexistent_key']
    except:
        logger.exception("Key error test")
    
    # Test exception logging when no exception is active
    logger.exception("No active exception test")
    
    print("Exception logging test completed")

if __name__ == "__main__":
    test_exception()
