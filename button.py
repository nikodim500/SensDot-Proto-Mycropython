"""Button handling module for SensDot (ESP32-C3, MicroPython)

Encapsulates:
- Reading developer-configured button pin and active level
- Debounce and long/very-long press detection at boot
- Optional deep sleep wake preparation (best-effort)

Notes:
- Deep sleep wake on ESP32-C3 may require RTC-capable pins (0..5). If the
  configured pin is not RTC-capable, wake preparation is skipped with a log.
- Hold timing is measured after boot/wake; the button wake itself (if enabled)
  brings the device out of deep sleep upon level.
"""

from machine import Pin
import time


class ButtonManager:
    def __init__(self, config_manager, logger=None):
        self.cfg = config_manager
        self.log = logger
        self.pin = None
        self.active_low = True
        self.debounce_ms = 50
        self.short_hold_s = 5
        self.long_hold_s = 20
        self.allow_deepsleep_wake = False

    def setup(self):
        bc = self.cfg.get_button_config()
        self.active_low = bool(bc.get('active_low', True))
        self.short_hold_s = int(bc.get('short_hold_s', 5))
        self.long_hold_s = int(bc.get('long_hold_s', 20))
        self.debounce_ms = int(bc.get('debounce_ms', 50))
        self.allow_deepsleep_wake = bool(bc.get('allow_deepsleep_wake', False))
        btn_pin = int(bc.get('button_pin', 9))
        # Try to setup pin with pull-up/down according to active level
        try:
            if self.active_low:
                self.pin = Pin(btn_pin, Pin.IN, Pin.PULL_UP)
            else:
                self.pin = Pin(btn_pin, Pin.IN, Pin.PULL_DOWN)
        except Exception:
            self.pin = Pin(btn_pin, Pin.IN)
        try:
            if self.log:
                self.log.info("Button on GPIO{} (active_{}, short={}s, long={}s)".format(
                    btn_pin, 'LOW' if self.active_low else 'HIGH', self.short_hold_s, self.long_hold_s))
        except:
            pass

    def _pressed(self):
        try:
            v = self.pin.value()
        except Exception:
            v = 1 if self.active_low else 0
        return (v == 0) if self.active_low else (v == 1)

    def _debounce(self):
        time.sleep_ms(self.debounce_ms)

    def check_hold_on_boot(self, max_wait_s=21):
        """If button is currently pressed at boot, measure hold duration.

        Returns: 'config_sta' (>= short), 'factory_reset' (>= long) or None
        """
        try:
            if not self._pressed():
                return None
            if self.log:
                self.log.info("Button pressed at boot; measuring hold...")
        except Exception:
            return None

        self._debounce()
        hold = 0.0
        while self._pressed() and hold < max_wait_s:
            time.sleep(0.1)
            hold += 0.1

        if hold >= self.long_hold_s - 0.5:
            if self.log:
                self.log.info("Button long hold (~{}s): factory reset".format(self.long_hold_s))
            return 'factory_reset'
        if hold >= self.short_hold_s - 0.5:
            if self.log:
                self.log.info("Button short hold (~{}s): STA portal".format(self.short_hold_s))
            return 'config_sta'
        return None

    def prepare_deepsleep_wake(self):
        """Best-effort to arm deep sleep wake on this button.
        Only logs if not possible; does not throw.
        """
        if not self.allow_deepsleep_wake:
            return False
        # Only RTC-capable pins can wake from deep sleep on ESP32-C3 (0..5)
        try:
            if self.pin is None:
                return False
            pnum = self.pin.id() if hasattr(self.pin, 'id') else None
            if pnum is None:
                return False
            if pnum not in (0, 1, 2, 3, 4, 5):
                if self.log:
                    self.log.warn("Button GPIO{} is not RTC-capable; cannot arm deep sleep wake".format(pnum))
                return False
            # Try platform-specific API
            try:
                import machine
                # Prefer level wake where available
                if hasattr(machine.Pin, 'wake_on_level'):
                    level = 0 if self.active_low else 1
                    machine.Pin.wake_on_level(self.pin, level)
                    if self.log:
                        self.log.info("Armed deep sleep wake on button (level={})".format(level))
                    return True
            except Exception as e:
                if self.log:
                    self.log.warn("Failed to arm button wake: {}".format(e))
                return False
        except Exception:
            return False
