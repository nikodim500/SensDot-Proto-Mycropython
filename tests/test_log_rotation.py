# test_log_rotation.py
# Test file rotation functionality on device

from logger import Logger
import time

def test_rotation():
    """Test log file rotation"""
    print("Testing log file rotation...")
    
    # Create logger with small file size for quick rotation
    logger = Logger(
        name="RotationTest",
        log_file="logs/rotation_test.log",
        max_file_size=500,  # Very small for quick rotation
        max_files=3,
        level=Logger.INFO,
        console_output=True
    )
    
    # Generate lots of log entries to trigger rotation
    for i in range(30):
        logger.info(f"This is log entry number {i:03d} - generating enough content to trigger file rotation when the file gets too large")
        time.sleep(0.1)
    
    print("Log rotation test completed")
    print("Check logs/ directory for rotation_test.log files")

if __name__ == "__main__":
    test_rotation()
