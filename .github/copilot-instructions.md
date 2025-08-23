# SensDot Proto Micropython — AI Agent Instructions

## Project Overview
ESP32-C3 SuperMini IoT device firmware for energy-efficient smarthome sensor monitoring. Uses MicroPython with WiFi AP configuration, MQTT communication, and modular sensor support.

## Architecture & Data Flow
- **Boot sequence**: Device checks for existing config → starts WiFi AP for setup OR connects to WiFi/MQTT for operation
- **Configuration flow**: WiFi AP (`SensDot-XXXX`) → Web interface (192.168.4.1) → Save config → Restart → Normal operation
- **Main operation**: WiFi connection → MQTT connection → Sensor reading loop → Deep sleep (planned)
- **Modules**: `config_manager.py` (persistent storage), `wifi_config.py` (AP + web server), `mqtt_client.py` (MQTT communication)

## Developer Workflows
- **Flash firmware**: Upload `main.py`, `lib/config_manager.py`, `lib/wifi_config.py`, `lib/mqtt_client.py` to ESP32-C3
- **First setup**: Device creates AP → Connect and configure via web → Device restarts into normal mode
- **Testing locally**: Run `python tests/test_config.py` (uses mocked MicroPython modules)
- **Reset config**: Delete `device_config.json` from device or implement hardware reset button

## Project Conventions
- **MicroPython specific**: Uses `machine`, `network`, `ubinascii`, `umqtt.simple` modules
- **Configuration storage**: JSON file (`device_config.json`) on device flash
- **Energy efficiency**: Designed for battery operation with planned deep sleep between readings
- **Modular sensors**: Add sensors iteratively in main cycle, publish data via MQTT
- **Error handling**: Connection failures trigger config reset and restart

## Integration Points
- **MQTT topics**: `{topic}/data` (sensor data), `{topic}/status` (device status), `{topic}/commands` (incoming commands)
- **Web interface**: Single-page HTML form with CSS styling for WiFi/MQTT configuration
- **Device ID**: Based on `machine.unique_id()`, used in AP SSID and MQTT client ID
- **JSON communication**: MQTT payloads include device metadata (timestamp, device_id)

## Example Patterns
- **Add sensor reading**:
  ```python
  # In main_cycle(), replace TODO sensor readings:
  sensor_data = {
      "temperature": read_temperature_sensor(),
      "humidity": read_humidity_sensor()
  }
  ```
- **MQTT command handling**: Extend `_message_callback()` in `mqtt_client.py`
- **Configuration parameter**: Add to `ConfigManager` set/get methods and web form

## Key Files & Directories
- `src/main.py` — Device boot logic and main sensor loop
- `lib/config_manager.py` — Persistent configuration (WiFi, MQTT settings)
- `lib/wifi_config.py` — WiFi AP mode and web configuration interface
- `lib/mqtt_client.py` — MQTT client with auto-reconnection and message handling
- `tests/test_config.py` — Local testing with mocked MicroPython modules

## Energy Efficiency Notes
- WiFi AP only during initial configuration
- Main loop designed for periodic readings + deep sleep
- MQTT keepalive and efficient publishing patterns
- Minimal memory footprint and garbage collection

---
For new sensors: extend `main_cycle()` sensor readings, maintain JSON data format. For new config: add to `ConfigManager` and web form. Keep MicroPython compatibility.
