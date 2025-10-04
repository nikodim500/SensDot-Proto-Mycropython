#!/usr/bin/env python3
"""
PIR Sensor Test Script for ESP32-C3 SuperMini
Tests PIR sensor on different GPIO pins to find correct mapping
"""

import time
import machine
from machine import Pin

def test_pir_pin(pin_num):
    """Test PIR sensor on a specific GPIO pin"""
    print(f"\n=== Testing PIR on GPIO{pin_num} ===")
    
    try:
        # Setup PIR pin with pull-down resistor
        pir = Pin(pin_num, Pin.IN, Pin.PULL_DOWN)
        
        print(f"GPIO{pin_num} initialized successfully")
        print("Monitoring for 10 seconds...")
        print("Wave your hand in front of the PIR sensor!")
        
        motion_detected = False
        for i in range(100):  # 10 seconds, check every 0.1s
            current_state = pir.value()
            if current_state == 1:
                if not motion_detected:
                    print(f"🚨 MOTION DETECTED on GPIO{pin_num}! ✅")
                    motion_detected = True
                print(f"PIR HIGH (motion) - {i/10:.1f}s")
            else:
                if motion_detected:
                    print(f"PIR returned to LOW - {i/10:.1f}s")
                    motion_detected = False
            
            time.sleep(0.1)
        
        final_state = pir.value()
        print(f"Final state: {'HIGH' if final_state else 'LOW'}")
        return motion_detected
        
    except Exception as e:
        print(f"❌ Error testing GPIO{pin_num}: {e}")
        return False

def main():
    """Test PIR on multiple potential GPIO pins"""
    print("🔍 PIR Sensor Troubleshooting Tool")
    print("=" * 40)
    print("ESP32-C3 SuperMini Pin Mapping:")
    print("6th leg from top = GPIO4 (most likely)")
    print("5th leg from top = GPIO5 (current config)")
    print("7th leg from top = GPIO6")
    print("4th leg from top = GPIO3")
    
    # Test potential PIR pins
    test_pins = [4, 5, 6, 3, 2, 7]  # GPIO4 most likely based on 6th leg
    
    results = {}
    for pin in test_pins:
        try:
            detected = test_pir_pin(pin)
            results[pin] = detected
        except KeyboardInterrupt:
            print("\nTest interrupted by user")
            break
        except Exception as e:
            print(f"Failed to test GPIO{pin}: {e}")
            results[pin] = False
    
    print("\n" + "=" * 40)
    print("📊 TEST RESULTS SUMMARY:")
    print("=" * 40)
    
    working_pins = []
    for pin, detected in results.items():
        status = "✅ MOTION DETECTED" if detected else "❌ No motion"
        print(f"GPIO{pin}: {status}")
        if detected:
            working_pins.append(pin)
    
    if working_pins:
        print(f"\n🎯 PIR sensor is working on: GPIO{working_pins}")
        print("Update your config_manager.py GPIO configuration!")
    else:
        print("\n⚠️  No motion detected on any pin. Check:")
        print("1. PIR sensor power connections (GND, 3.3V)")
        print("2. PIR sensor data wire connection")
        print("3. PIR sensor needs 30-60 seconds to stabilize after power-on")
        print("4. Try moving closer to the sensor")
    
    print("\nDone! Press Ctrl+C to exit REPL")

if __name__ == '__main__':
    main()
