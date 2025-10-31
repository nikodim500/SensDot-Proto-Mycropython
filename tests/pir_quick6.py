# Quick PIR test for current wiring on GPIO6 (NOT deep-sleep wake capable on ESP32-C3)
# Purpose: just confirm AS312 output toggles HIGH on motion.
# After confirming, rewire to GPIO5 (or 4) for deep sleep wake capability.

import time
from machine import Pin

PIR_PIN = 6
STABILIZE = 20      # seconds to let sensor settle (can increase to 40 on first power-up)
OBSERVE   = 40      # seconds to monitor
PERIOD    = 0.1

print("=== PIR QUICK TEST (GPIO6) ===")
print("Stabilizing sensor, do NOT move in front of it...")
for remaining in range(STABILIZE, 0, -5):
    print(f"  {remaining}s left...")
    time.sleep(5)

pir = Pin(PIR_PIN, Pin.IN)  # try without pull first; add Pin.PULL_DOWN if always HIGH
print("Stabilization complete. Start moving in front of the sensor.")

last = pir.value()
start = time.ticks_ms()
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
    print(f"Detected {motion_events} motion event(s) on GPIO{PIR_PIN}.")
    print("Reminder: move wire to GPIO5 later for deep-sleep wake.")
else:
    print("No motion events detected. If this repeats: \n - Wait longer (60s) \n - Check wiring (VOUT top -> pin, GND, 3V3) \n - Try Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN) \n - Ensure lens unobstructed")
print("Done.")
