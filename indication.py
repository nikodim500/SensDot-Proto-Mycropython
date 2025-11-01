"""Indication manager for SensDot (ESP32-C3, MicroPython)

Centralizes visual/audible indications:
- Internal status LED (GPIO8, inverted logic on ESP32-C3 SuperMini)
- External LED (GPIO10 default, normal logic)
- Future: buzzer hooks (no-op for now)

Design:
- Runtime indications (sensor/MQTT blinks) are gated by existing config flag
  gpio.external_led_enabled. When False, all runtime LED actions are suppressed
  (both internal and external). AP mode blink remains active regardless.
- AP blink selects the visible LED: external if enabled, else internal.
- Safe-off handling for external LED when disabled, considering active-low wiring.
"""

from machine import Pin, Timer
import time


class IndicationManager:
    def __init__(self, config_manager, logger=None):
        self.cfgm = config_manager
        self.log = logger
        # Pins/objects
        self.status_led = None   # internal (inverted)
        self.external_led = None # external (normal)
        # Flags
        self.runtime_enabled = True    # gate for runtime indications
        self.external_led_enabled = True
        self.external_active_low = False
        # AP blink state
        self._ap_timer = None
        self._ap_led = None
        self._ap_inverted = False
        self._ap_state = False

    # ---------- Setup ----------
    def setup(self):
        gpio = self.cfgm.get_gpio_config() or {}
        self.external_led_enabled = bool(gpio.get('external_led_enabled', True))
        self.external_active_low = bool(gpio.get('external_led_active_low', False))
        # Gate runtime indications with the existing checkbox
        self.runtime_enabled = self.external_led_enabled
        try:
            # Internal status LED (inverted)
            self.status_led = Pin(gpio.get('status_led_pin', 8), Pin.OUT)
            # Start OFF (inverted)
            try:
                self.status_led.on()
            except:
                pass
            if self.log:
                self.log.info("Status LED initialized on GPIO{}".format(gpio.get('status_led_pin', 8)))
        except Exception as e:
            if self.log:
                self.log.warn("Status LED init failed: {}".format(e))
            self.status_led = None

        # External LED handling
        try:
            ext_pin = gpio.get('external_led_pin', 10)
            if self.external_led_enabled:
                # Initialize external LED (normal logic)
                try:
                    self.external_led = Pin(ext_pin, Pin.OUT)
                    # Ensure OFF initially
                    try:
                        self.external_led.off()
                    except:
                        pass
                    if self.log:
                        self.log.info("External LED initialized on GPIO{} (enabled)".format(ext_pin))
                except Exception as _ie:
                    self.external_led = None
                    if self.log:
                        self.log.warn("External LED init failed: {}".format(_ie))
            else:
                # Ensure safe OFF state when disabled
                self.ensure_external_safe_off()
                if self.log:
                    self.log.info("External LED disabled by config (GPIO{} set safe OFF)".format(ext_pin))
        except Exception as e:
            if self.log:
                self.log.warn("External LED handling failed: {}".format(e))
            self.external_led = None

        # Note runtime gate state
        try:
            if self.log:
                if not self.runtime_enabled:
                    self.log.info("Runtime LED indications are DISABLED by config (AP mode unaffected)")
                else:
                    self.log.debug("Runtime LED indications enabled")
        except:
            pass

    # ---------- External LED safe-off ----------
    def ensure_external_safe_off(self):
        """Drive or configure the external LED pin to a safe OFF state respecting wiring.
        Uses high-Z with pull where available.
        """
        try:
            gpio = self.cfgm.get_gpio_config() or {}
            ext_pin = gpio.get('external_led_pin', 10)
            active_low = bool(gpio.get('external_led_active_low', False))
            if active_low:
                # OFF = high; prefer input with pull-up, drive high once
                try:
                    Pin(ext_pin, Pin.OUT).on()
                except:
                    pass
                try:
                    Pin(ext_pin, Pin.IN, Pin.PULL_UP)
                except:
                    pass
            else:
                # OFF = low; prefer input with pull-down, else hold low
                try:
                    Pin(ext_pin, Pin.OUT).off()
                except:
                    pass
                try:
                    Pin(ext_pin, Pin.IN, Pin.PULL_DOWN)
                except:
                    try:
                        Pin(ext_pin, Pin.OUT).off()
                    except:
                        pass
        except Exception as e:
            if self.log:
                self.log.warn("External LED safe-off failed: {}".format(e))

    # ---------- Runtime LED API ----------
    def on(self):
        if not self.runtime_enabled:
            return
        try:
            if self.status_led:
                # Inverted: on() -> OFF; off() -> ON
                self.status_led.off()
        except:
            pass
        try:
            if self.external_led and self.external_led_enabled:
                self.external_led.on()
        except:
            pass

    def off(self):
        if not self.runtime_enabled:
            return
        try:
            if self.status_led:
                self.status_led.on()
        except:
            pass
        try:
            if self.external_led and self.external_led_enabled:
                self.external_led.off()
        except:
            pass

    def blink(self, times=3, delay=0.2, final_on=True):
        if not self.runtime_enabled:
            return
        have_int = bool(self.status_led)
        have_ext = bool(self.external_led and self.external_led_enabled)
        if not (have_int or have_ext):
            return
        for _ in range(times):
            try:
                if have_int:
                    self.status_led.on()   # internal OFF
                if have_ext:
                    self.external_led.off()  # external OFF
            except:
                pass
            time.sleep(delay)
            try:
                if have_int:
                    self.status_led.off()  # internal ON
                if have_ext:
                    self.external_led.on()   # external ON
            except:
                pass
            time.sleep(delay)
        if not final_on:
            try:
                if have_int:
                    self.status_led.on()
                if have_ext:
                    self.external_led.off()
            except:
                pass

    # ---------- AP Blink (independent of runtime gate) ----------
    def _ap_vis_on(self):
        try:
            if self._ap_inverted:
                self._ap_led.off()
            else:
                self._ap_led.on()
        except:
            pass

    def _ap_vis_off(self):
        try:
            if self._ap_inverted:
                self._ap_led.on()
            else:
                self._ap_led.off()
        except:
            pass

    def ap_blink_start(self, period_ms=600):
        """Start AP mode blinking. Chooses external if enabled, else internal."""
        # Choose LED and inversion: external (normal), else internal (inverted)
        gpio = self.cfgm.get_gpio_config() or {}
        use_external = bool(gpio.get('external_led_enabled', True))
        if use_external:
            pin = gpio.get('external_led_pin', 10)
            self._ap_inverted = False
        else:
            pin = gpio.get('status_led_pin', 8)
            self._ap_inverted = True
        try:
            self._ap_led = Pin(pin, Pin.OUT)
            # Start with OFF
            self._ap_vis_off()
        except Exception as e:
            if self.log:
                self.log.warn("AP LED init failed: {}".format(e))
            self._ap_led = None
            return

        def _cb(t):
            try:
                self._ap_state = not self._ap_state
                if self._ap_state:
                    self._ap_vis_on()
                else:
                    self._ap_vis_off()
            except:
                pass

        # Start timer with fallback index
        try:
            self._ap_timer = Timer(1)
            self._ap_timer.init(period=period_ms, mode=Timer.PERIODIC, callback=_cb)
        except Exception:
            try:
                self._ap_timer = Timer(0)
                self._ap_timer.init(period=period_ms, mode=Timer.PERIODIC, callback=_cb)
            except Exception as e:
                if self.log:
                    self.log.warn("AP Timer start failed: {}".format(e))
                self._ap_timer = None

    def ap_blink_stop(self):
        try:
            if self._ap_timer:
                try:
                    self._ap_timer.deinit()
                except:
                    pass
                self._ap_timer = None
            if self._ap_led:
                self._ap_vis_off()
        except:
            pass

    # ---------- Buzzer hooks (future) ----------
    def buzz_on(self):
        pass

    def buzz_off(self):
        pass

    def beep(self, times=1, freq=2000, duration_ms=100):
        pass
