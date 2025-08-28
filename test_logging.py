# test_logging.py
# Test script for the SensDot logging system
# Run this to verify logging functionality

from logger import Logger, setup_logging
from config_manager import ConfigManager
import time

def test_basic_logging():
    """Test basic logging functionality"""
    print("=== Testing Basic Logging ===")
    
    # Create a logger with small file size for testing rotation
    logger = Logger(
        name="TestLogger",
        log_file="test.log",
        max_file_size=1024,  # 1KB for quick rotation testing
        max_files=3,
        level=Logger.DEBUG,
        console_output=True
    )
    
    # Test different log levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warn("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    # Test logging a lot of data to trigger rotation
    print("\n=== Testing File Rotation ===")
    for i in range(20):
        logger.info(f"Log entry #{i:03d} - generating content to test file rotation functionality")
        time.sleep(0.1)  # Small delay to make timestamps different
    
    # Test exception logging
    print("\n=== Testing Exception Logging ===")
    try:
        result = 1 / 0  # This will raise ZeroDivisionError
    except:
        logger.exception("Caught an exception during testing")
    
    # Show log statistics
    stats = logger.get_log_stats()
    print(f"\n=== Log Statistics ===")
    for key, value in stats.items():
        print(f"{key}: {value}")

def test_config_integration():
    """Test logging integration with configuration"""
    print("\n\n=== Testing Config Integration ===")
    
    # Create a config manager (will work even without device)
    config = ConfigManager()
    
    # Set logging configuration
    config.set_logging_config(
        log_level="DEBUG",
        log_file_size=2048,
        log_files_count=2,
        enable_file_logging=True
    )
    
    # Setup logging with config
    logger = setup_logging(config, console_output=True)
    
    logger.info("Logger initialized with configuration")
    logger.debug("Debug mode enabled through configuration")
    
    # Test logging config retrieval
    log_config = config.get_logging_config()
    logger.info(f"Logging config: {log_config}")

def test_global_logger():
    """Test global logger functions"""
    print("\n\n=== Testing Global Logger Functions ===")
    
    # Import global functions
    from logger import debug, info, warn, error, critical, exception
    
    # These will use the global logger instance
    debug("Global debug message")
    info("Global info message") 
    warn("Global warning message")
    error("Global error message")
    critical("Global critical message")

def main():
    """Run all logging tests"""
    print("SensDot Logging System Test")
    print("=" * 40)
    
    test_basic_logging()
    test_config_integration()
    test_global_logger()
    
    print("\n" + "=" * 40)
    print("Logging tests completed!")
    print("Check the generated log files:")
    print("- test.log (and test.log.1, test.log.2 if rotation occurred)")
    print("- sensdot.log (from config integration test)")

if __name__ == "__main__":
    main()
