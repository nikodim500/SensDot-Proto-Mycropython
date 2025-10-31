# Simple PIR test on GPIO5 (no deep sleep)
# Purpose: verify motion events after relocation from GPIO6 to GPIO5.
# Run: mpremote connect port:COM3 run tests/pir_gpio5_simple.py

import time
from machine import Pin

PIR_PIN = 5
STABILIZE = 20   # seconds (increase to 40 on very first power-up)
OBSERVE   = 35   # seconds to watch after stabilization
PERIOD    = 0.1

print("=== PIR SIMPLE TEST (GPIO5) ===")
print("Stabilizing sensor, keep area still...")
for remaining in range(STABILIZE, 0, -5):
    print(f"  {remaining}s left...")
    time.sleep(5)

# Try with pull-down first; if always HIGH, remove it.
try:
    pir = Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN)
except Exception:
    pir = Pin(PIR_PIN, Pin.IN)

print("Stabilization done. Move in front of sensor now.")
start = time.ticks_ms()
last = pir.value()
motion_events = 0

while time.ticks_diff(time.ticks_ms(), start) < OBSERVE * 1000:
    v = pir.value()
    if v != last:
        if v == 1:
            motion_events += 1
            print(f"{(time.ticks_ms()-start)//1000:>2}s: MOTION HIGH (event #{motion_events})")
        else:
            print(f"{(time.ticks_ms()-start)//1000:>2}s: returned LOW")
        last = v
    time.sleep(PERIOD)

print("=== SUMMARY ===")
if motion_events:
    print(f"GPIO{PIR_PIN} ACTIVE. {motion_events} event(s) captured.")
    print("Ready to integrate for deep sleep wake.")
else:
    print("No events. If unexpected: \n - Recheck wiring (VOUT->GPIO5, GND, 3V3)\n - Wait longer (60s initial warm-up)\n - Remove PULL_DOWN and retry")
print("Done.")
