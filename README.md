# SensDot Proto Micropython

ESP32-C3 SuperMini based IoT smarthome device firmware for energy-efficient sensor monitoring.

## Project Structure
- `src/main.py` : Main device firmware entry point
- `lib/config_manager.py` : Configuration storage and management
- `lib/wifi_config.py` : WiFi AP and web-based configuration server
- `tests/` : Test scripts for local development

## Device Features
- **Energy Efficient**: Deep sleep mode with configurable intervals (default: 1 minute)
- **Auto Configuration**: Modern web interface in WiFi AP mode for initial setup
- **Hardware Reset**: Button-based configuration reset (hold for 3 seconds)
- **MQTT Integration**: Configurable MQTT broker connection for IoT communication
- **Advanced Settings**: Configurable sleep intervals, sensor timing, and debug mode
- **Persistent Settings**: Configuration stored on device flash memory
- **Iterative Development**: Modular design for adding sensors progressively

## Hardware Requirements
- ESP32-C3 SuperMini development board
- MicroPython firmware installed
- Reset button connected to GPIO9 (with pull-up resistor)
- Optional: Sensors (to be added iteratively)

## Initial Setup

### 1. Flash MicroPython Firmware
Download and flash MicroPython firmware for ESP32-C3 to your device.

### 2. Upload Project Files
Upload the following files to your ESP32-C3 root directory:
```
main.py
config_manager.py
wifi_config.py
mqtt_client.py
```

Optional: Create `lib/` directory for future sensor libraries.

### 3. First Boot Configuration
1. Reset/power on the device
2. Device will create WiFi AP: `SensDot-XXXX` (XXXX = last 4 chars of device ID)
3. Connect to WiFi AP with password: `sensdot123`
4. Navigate to `http://192.168.4.1` in your browser
5. Configure WiFi and MQTT settings through web interface
6. Device will restart and connect to your network

## Configuration Parameters

### WiFi Settings
- **SSID**: Your home WiFi network name
- **Password**: Your WiFi password

### MQTT Settings
- **Broker**: MQTT broker IP address or hostname
- **Port**: MQTT broker port (default: 1883)
- **Username**: MQTT username (optional)
- **Password**: MQTT password (optional)
- **Topic**: MQTT topic prefix (default: `sensdot/DEVICE_ID`)

### Advanced Settings
- **Deep Sleep Interval**: How long to sleep between sensor readings (10-3600 seconds, default: 60)
- **Sensor Interval**: How often to read sensors when awake (5-300 seconds, default: 30)
- **Debug Mode**: Enable detailed logging (increases power consumption)

## Development Workflow

### Local Testing
```powershell
cd tests
python test_config.py
```

### Flash to Device
Use your preferred tool (ampy, rshell, Thonny, etc.):
```powershell
# Example with ampy
ampy --port COM3 put src/main.py main.py
ampy --port COM3 put lib/config_manager.py lib/config_manager.py
ampy --port COM3 put lib/wifi_config.py lib/wifi_config.py
```

### Reset Configuration
**Hardware Reset Button:**
- Connect a button between GPIO9 and GND (with pull-up resistor)
- Hold button for 3 seconds during boot to reset configuration
- Device will restart in AP configuration mode

**Manual Reset:**
- Delete `device_config.json` from device storage
- Device will start in configuration mode on next boot

## Energy Efficiency Features
- **Deep Sleep Mode**: Configurable sleep intervals (default: 1 minute between readings)
- **Wake-on-Demand**: Device wakes up, reads sensors, publishes data, then sleeps
- **WiFi AP only during configuration**: Normal operation uses station mode only
- **Efficient MQTT communication**: Clean connect/disconnect cycles
- **Minimal memory footprint**: Optimized for battery operation
- **Configurable intervals**: Balance between data frequency and battery life

## Next Development Steps
1. ✅ Basic configuration system
2. ✅ Modern WiFi AP with responsive web interface
3. ✅ MQTT configuration and client
4. ✅ Hardware reset button (GPIO9)
5. ✅ Deep sleep power management with configurable intervals
6. ✅ Advanced configuration options
7. ⏳ MQTT client auto-reconnection improvements
8. ⏳ Sensor abstraction layer
9. ⏳ Battery voltage monitoring (ADC)
10. ⏳ Temperature/humidity sensor (DHT22/SHT30)
11. ⏳ OTA firmware updates
12. ⏳ Watchdog timer implementation

## Troubleshooting

### Device doesn't start AP mode
- Check if `device_config.json` exists and is valid
- Verify MicroPython installation
- Check serial output for error messages

### Can't connect to WiFi AP
- Verify AP SSID format: `SensDot-XXXX`
- Default password: `sensdot123`
- Check device is in configuration mode

### Configuration not saving
- Ensure sufficient flash memory
- Check file permissions
- Verify JSON format in web form

## Contributing
This is a prototype project. Feel free to extend with additional sensors and features while maintaining the energy-efficient design principles.
