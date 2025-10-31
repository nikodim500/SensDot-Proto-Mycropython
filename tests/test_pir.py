#!/usr/bin/env python3
"""
Minimal PIR Sensor Test for ESP32-C3 (AS312 / AM312)
Goal: verify that PIR toggles HIGH on motion (no deep sleep yet)

Usage:
  mpremote connect port:COM3 run tests/test_pir.py

Wiring (AS312 facing you, single top pin):
  Top single pin  -> VOUT -> GPIO5 (recommended RTC wake capable) or GPIO4
  Bottom left     -> GND
  Bottom right    -> 3V3

Notes:
  - AS312 needs 20–60s stabilization after power
  - Output stays HIGH ~2s per trigger
  - Use GPIO0..GPIO5 for future deep sleep wake (RTC GPIO range)
"""

import time
from machine import Pin

# Primary (recommended) PIR pin for wake-capable setup
PRIMARY_PIN = 5   # RTC GPIO (0..5). Change in one place if rewired.
# Secondary pin to probe if unsure actual wiring
SECONDARY_PIN = 4

STABILIZE_SECONDS = 25   # Can reduce after first confirmation
OBSERVE_SECONDS   = 40
SAMPLE_PERIOD     = 0.1


def init_pir(pin_num):
    # Some boards work better without explicit pull; try PULL_DOWN first
    try:
        return Pin(pin_num, Pin.IN, Pin.PULL_DOWN)
    except Exception:
        return Pin(pin_num, Pin.IN)


def observe(pir, label):
    print(f"\n--- Observing {label} for {OBSERVE_SECONDS}s ---")
    motion_events = 0
    last_state = pir.value()
    start = time.ticks_ms()
    while (time.ticks_ms() - start) < OBSERVE_SECONDS * 1000:
        v = pir.value()
        if v != last_state:
            if v == 1:
                motion_events += 1
                print(f"{time.ticks_ms()//1000}s: MOTION HIGH ✅ (event #{motion_events})")
            else:
                print(f"{time.ticks_ms()//1000}s: returned LOW")
            last_state = v
        time.sleep(SAMPLE_PERIOD)
    print(f"Total motion events on {label}: {motion_events}\n")
    return motion_events


def main():
    print("=== PIR Quick Test (AS312) ===")
    print(f"Primary RTC-capable PIR pin: GPIO{PRIMARY_PIN}")
    print(f"Secondary probe pin: GPIO{SECONDARY_PIN}")
    print("Stabilizing sensor (avoid movement)...")

    # Basic stabilization countdown
    for remaining in range(STABILIZE_SECONDS, 0, -5):
        print(f"  {remaining}s left...")
        time.sleep(5)
    print("Stabilization phase complete. Start moving in front of the sensor.")

    # Test primary pin first
    pir_primary = init_pir(PRIMARY_PIN)
    events_primary = observe(pir_primary, f"GPIO{PRIMARY_PIN}")

    # If no events, optionally probe secondary automatically
    events_secondary = 0
    if events_primary == 0:
        print("No motion captured on primary. Probing secondary pin...")
        pir_secondary = init_pir(SECONDARY_PIN)
        # Shorter observe on secondary (reuse same duration for clarity)
        events_secondary = observe(pir_secondary, f"GPIO{SECONDARY_PIN}")

    # Summary
    print("=== SUMMARY ===")
    if events_primary > 0:
        print(f"PIR ACTIVE on GPIO{PRIMARY_PIN} (recommended for deep sleep wake).")
    elif events_secondary > 0:
        print(f"PIR ACTIVE on GPIO{SECONDARY_PIN}. Consider rewiring to GPIO{PRIMARY_PIN} for wake.")
    else:
        print("No motion events detected. Check wiring, power, and wait longer (60s) after power-up.")
        print("Checklist:\n - VOUT top single pin -> chosen GPIO (0..5)\n - GND -> common ground\n - VCC -> stable 3.3V\n - No metal shielding lens\n - Wait full stabilization")

    print("Done.")


if __name__ == "__main__":
    main()
