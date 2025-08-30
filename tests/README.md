# SensDot Tests Directory

This directory contains test files for the SensDot ESP32 firmware components.

## Test Files

### `test_config.py`
Tests the configuration manager functionality with mocked MicroPython modules.
- Config file read/write operations
- WiFi, MQTT, and NTP configuration handling
- Default value validation

### `test_logging.py`
Tests the logging system functionality.
- Basic logging operations
- Log level filtering
- File output verification
- Memory usage testing

### `test_log_rotation.py`
Tests log file rotation on device.
- File size-based rotation
- Multiple log file handling
- Cleanup operations

### `test_ntp.py`
Tests NTP time synchronization functionality.
- NTP server communication
- Timezone offset application
- DST calculations
- Time formatting

### `test_webserver.py`
Web interface test server for Windows development.
- Simulates ESP32 web configuration interface
- Allows testing UI changes without device
- Run with: `python tests\test_webserver.py`

## Running Tests

### Local Testing (Windows)
```bash
# Configuration tests
python tests\test_config.py

# Logging tests  
python tests\test_logging.py

# NTP functionality tests
python tests\test_ntp.py

# Web interface testing
python tests\test_webserver.py
# Then open http://localhost:8080
```

### Device Testing
Upload the main firmware files to ESP32 and use the device logs to verify functionality.

## Notes

- Tests that use MicroPython modules include mock implementations
- Web server test requires standard Python libraries only
- Configuration tests create temporary files for testing
- All tests are designed to run independently
