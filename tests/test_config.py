# test_config.py
# Simple test script for configuration modules (run locally for testing)

# Mock the MicroPython modules for testing
class MockMachine:
    @staticmethod
    def unique_id():
        return b'\x12\x34\x56\x78'
    
    @staticmethod
    def reset():
        print("Device would restart here")

class MockNetwork:
    AP_IF = 1
    
    class WLAN:
        def __init__(self, interface):
            self.interface = interface
        
        def active(self, state=None):
            if state is not None:
                print(f"WiFi AP {'enabled' if state else 'disabled'}")
            return True
        
        def config(self, **kwargs):
            print(f"WiFi AP configured: {kwargs}")
        
        def ifconfig(self):
            return ('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8')

# Mock imports
import sys
sys.modules['machine'] = MockMachine()
sys.modules['network'] = MockNetwork()
sys.modules['ubinascii'] = type('MockUbinascii', (), {
    'hexlify': lambda x: b'1234567890abcdef'
})()

# Add lib to path
sys.path.append('lib')

# Test imports
try:
    from config_manager import ConfigManager
    print("✓ ConfigManager imported successfully")
    
    # Test basic functionality
    config = ConfigManager()
    print(f"Device ID: {config.get_device_id()}")
    print(f"Is configured: {config.is_configured()}")
    
    # Test configuration
    config.set_wifi_config("TestNetwork", "password123")
    config.set_mqtt_config("192.168.1.100", 1883, "user", "pass", "sensors/device1")
    
    print("✓ Configuration test passed")
    
except Exception as e:
    print(f"✗ ConfigManager test failed: {e}")

try:
    from wifi_config import WiFiConfigServer
    print("✓ WiFiConfigServer imported successfully")
except Exception as e:
    print(f"✗ WiFiConfigServer test failed: {e}")

print("\nTest completed!")
