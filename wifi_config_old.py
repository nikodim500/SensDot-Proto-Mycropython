# wifi_config.py
# WiFi Access Point and Web Configuration Server
# Provides web interface for device configuration

import network
import socket
import time

class WiFiConfigServer:
    """WiFi Access Point with web-based configuration interface"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.ap = None
        self.server_socket = None
    
    def start_config_server(self):
        """Start WiFi AP and web server for configuration"""
        print("Starting configuration server...")
        
        # Create access point
        self.ap = network.WLAN(network.AP_IF)
        self.ap.active(True)
        
        # Configure AP settings
        device_id = self.config_manager.get_device_id()
        ap_ssid = f"SensDot-{device_id[-4:]}"  # Last 4 chars of device ID
        
        # Create open network (no password) for easier initial connection
        self.ap.config(essid=ap_ssid, authmode=0)  # authmode=0 means open network
        
        print(f"WiFi AP started: {ap_ssid}")
        print("Network: Open (no password required)")
        print(f"IP: {self.ap.ifconfig()[0]}")
        
        # Start web server
        self._start_web_server()
    
    def _start_web_server(self):
        """Start the web server for configuration"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', 80))
        self.server_socket.listen(1)
        
        print("Web server started on port 80")
        print("Connect to WiFi and navigate to http://192.168.4.1")
        
        while True:
            try:
                client_socket, addr = self.server_socket.accept()
                print(f"Connection from {addr}")
                self._handle_request(client_socket)
            except Exception as e:
                print(f"Server error: {e}")
                time.sleep(1)
    
    def _handle_request(self, client_socket):
        """Handle HTTP request"""
        try:
            request = client_socket.recv(1024).decode('utf-8')
            
            if 'POST /config' in request:
                # Handle configuration submission
                self._handle_config_post(request, client_socket)
            elif 'GET /status' in request:
                # Handle status request
                self._send_status_response(client_socket)
            else:
                # Send configuration form
                self._send_config_form(client_socket)
                
        except Exception as e:
            print(f"Request handling error: {e}")
        finally:
            client_socket.close()
    
    def _handle_config_post(self, request, client_socket):
        """Handle configuration form submission"""
        try:
            # Parse form data from request body
            body_start = request.find('\r\n\r\n')
            if body_start == -1:
                self._send_error_response(client_socket, "Invalid request")
                return
            
            body = request[body_start + 4:]
            config_data = self._parse_form_data(body)
            
            # Validate required fields
            required_fields = ['wifi_ssid', 'wifi_password', 'mqtt_broker']
            if not all(field in config_data for field in required_fields):
                self._send_error_response(client_socket, "Missing required fields")
                return
            
            # Save WiFi configuration
            self.config_manager.set_wifi_config(
                config_data['wifi_ssid'],
                config_data['wifi_password']
            )
            
            # Save MQTT configuration
            mqtt_port = int(config_data.get('mqtt_port', 1883))
            self.config_manager.set_mqtt_config(
                config_data['mqtt_broker'],
                mqtt_port,
                config_data.get('mqtt_username', ''),
                config_data.get('mqtt_password', ''),
                config_data.get('mqtt_topic', '')
            )
            
            # Save advanced configuration
            sleep_interval = int(config_data.get('sleep_interval', 60))
            sensor_interval = int(config_data.get('sensor_interval', 30))
            debug_mode = config_data.get('debug_mode') == 'on'
            self.config_manager.set_advanced_config(sleep_interval, sensor_interval, debug_mode)
            
            print("Configuration saved successfully")
            self._send_success_response(client_socket)
            
            # Schedule restart after a short delay
            import _thread
            _thread.start_new_thread(self._restart_device, ())
            
        except Exception as e:
            print(f"Configuration error: {e}")
            self._send_error_response(client_socket, f"Configuration error: {e}")
    
    def _parse_form_data(self, body):
        """Parse URL-encoded form data"""
        data = {}
        if body:
            pairs = body.split('&')
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    # Simple URL decode
                    key = key.replace('+', ' ').replace('%20', ' ')
                    value = value.replace('+', ' ').replace('%20', ' ')
                    data[key] = value
        return data
    
    def _send_config_form(self, client_socket):
        """Send HTML configuration form"""
        device_id = self.config_manager.get_device_id()
        current_config = self.config_manager.get_all_config()
        advanced_config = self.config_manager.get_advanced_config()
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>SensDot Configuration</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ 
            max-width: 600px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 16px; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
        .device-info {{ 
            background: rgba(255,255,255,0.1); 
            padding: 15px; 
            border-radius: 8px; 
            margin-top: 15px;
            font-size: 14px;
        }}
        .form-content {{ padding: 30px; }}
        .section {{ margin-bottom: 30px; }}
        .section h3 {{ 
            color: #374151; 
            font-size: 20px; 
            margin-bottom: 15px; 
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 8px;
        }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ 
            display: block; 
            margin-bottom: 6px; 
            font-weight: 600; 
            color: #374151;
            font-size: 14px;
        }}
        input[type="text"], input[type="password"], input[type="number"], select {{ 
            width: 100%; 
            padding: 12px 16px; 
            border: 2px solid #e5e7eb; 
            border-radius: 8px; 
            font-size: 16px;
            transition: border-color 0.3s ease;
            background: #f9fafb;
        }}
        input:focus, select:focus {{ 
            outline: none; 
            border-color: #4f46e5; 
            background: white;
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }}
        .checkbox-group {{
            display: flex;
            align-items: center;
            margin-top: 15px;
        }}
        .checkbox-group input[type="checkbox"] {{
            width: auto;
            margin-right: 10px;
            transform: scale(1.2);
        }}
        .checkbox-group label {{
            margin-bottom: 0;
            cursor: pointer;
        }}
        button {{ 
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: white; 
            padding: 16px 32px; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer; 
            width: 100%;
            font-size: 16px;
            font-weight: 600;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        button:hover {{ 
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(79, 70, 229, 0.3);
        }}
        .advanced-toggle {{
            background: #6b7280;
            margin-bottom: 20px;
            padding: 12px 24px;
            font-size: 14px;
        }}
        .advanced-section {{
            display: none;
            background: #f8fafc;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }}
        .advanced-section.show {{ display: block; }}
        .help-text {{
            font-size: 12px;
            color: #6b7280;
            margin-top: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌐 SensDot Device</h1>
            <p>Smart Home IoT Configuration</p>
            <div class="device-info">
                <strong>Device ID:</strong> {device_id}<br>
                <strong>Status:</strong> ⚙️ Awaiting Configuration<br>
                <strong>Hardware:</strong> ESP32-C3 SuperMini
            </div>
        </div>
        
        <div class="form-content">
            <form method="POST" action="/config">
                <div class="section">
                    <h3>📶 WiFi Network</h3>
                    <div class="form-group">
                        <label for="wifi_ssid">Network Name (SSID):</label>
                        <input type="text" id="wifi_ssid" name="wifi_ssid" value="{current_config.get('wifi_ssid', '')}" required>
                        <div class="help-text">Enter your home WiFi network name</div>
                    </div>
                    <div class="form-group">
                        <label for="wifi_password">WiFi Password:</label>
                        <input type="password" id="wifi_password" name="wifi_password" value="{current_config.get('wifi_password', '')}" required>
                        <div class="help-text">Your WiFi network password</div>
                    </div>
                </div>
                
                <div class="section">
                    <h3>📡 MQTT Broker</h3>
                    <div class="form-group">
                        <label for="mqtt_broker">Broker Address:</label>
                        <input type="text" id="mqtt_broker" name="mqtt_broker" value="{current_config.get('mqtt_broker', '')}" required placeholder="192.168.1.100 or mqtt.home.lan">
                        <div class="help-text">IP address or hostname of your MQTT broker</div>
                    </div>
                    <div class="form-group">
                        <label for="mqtt_port">Port:</label>
                        <input type="number" id="mqtt_port" name="mqtt_port" value="{current_config.get('mqtt_port', 1883)}" min="1" max="65535">
                        <div class="help-text">Usually 1883 for MQTT or 8883 for MQTT over SSL</div>
                    </div>
                    <div class="form-group">
                        <label for="mqtt_username">Username (optional):</label>
                        <input type="text" id="mqtt_username" name="mqtt_username" value="{current_config.get('mqtt_username', '')}">
                    </div>
                    <div class="form-group">
                        <label for="mqtt_password">Password (optional):</label>
                        <input type="password" id="mqtt_password" name="mqtt_password" value="{current_config.get('mqtt_password', '')}">
                    </div>
                    <div class="form-group">
                        <label for="mqtt_topic">Topic Prefix:</label>
                        <input type="text" id="mqtt_topic" name="mqtt_topic" value="{current_config.get('mqtt_topic', 'sensdot/' + device_id)}" placeholder="sensdot/{device_id}">
                        <div class="help-text">Base topic for all device messages</div>
                    </div>
                </div>
                
                <button type="button" class="advanced-toggle" onclick="toggleAdvanced()">
                    ⚡ Advanced Settings
                </button>
                
                <div class="advanced-section" id="advanced">
                    <h3>⚡ Power Management</h3>
                    <div class="form-group">
                        <label for="sleep_interval">Deep Sleep Interval (seconds):</label>
                        <input type="number" id="sleep_interval" name="sleep_interval" value="{advanced_config.get('sleep_interval', 60)}" min="10" max="3600">
                        <div class="help-text">How long to sleep between sensor readings (60s = 1 minute)</div>
                    </div>
                    <div class="form-group">
                        <label for="sensor_interval">Sensor Reading Interval (seconds):</label>
                        <input type="number" id="sensor_interval" name="sensor_interval" value="{advanced_config.get('sensor_interval', 30)}" min="5" max="300">
                        <div class="help-text">How often to read sensors when awake</div>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="debug_mode" name="debug_mode" {'checked' if advanced_config.get('debug_mode', False) else ''}>
                        <label for="debug_mode">Enable Debug Mode</label>
                    </div>
                    <div class="help-text">Enables detailed logging (increases power consumption)</div>
                </div>
                
                <button type="submit">💾 Save Configuration</button>
            </form>
        </div>
    </div>
    
    <script>
        function toggleAdvanced() {{
            const section = document.getElementById('advanced');
            const button = document.querySelector('.advanced-toggle');
            section.classList.toggle('show');
            button.textContent = section.classList.contains('show') ? '⚡ Hide Advanced Settings' : '⚡ Advanced Settings';
        }}
    </script>
</body>
</html>"""
        
        response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(html)}\r\n\r\n{html}"
        client_socket.send(response.encode())
    
    def _send_success_response(self, client_socket):
        """Send success response"""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>Configuration Saved</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="8;url=/">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container { 
            background: white; 
            padding: 40px; 
            border-radius: 16px; 
            text-align: center;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            max-width: 500px;
            width: 100%;
        }
        .success-icon { 
            font-size: 64px; 
            color: #10b981; 
            margin-bottom: 20px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        h1 { 
            color: #065f46; 
            font-size: 28px; 
            margin-bottom: 16px; 
        }
        p { 
            color: #374151; 
            font-size: 16px; 
            line-height: 1.6;
            margin-bottom: 12px;
        }
        .countdown {
            background: #f0fdf4;
            padding: 16px;
            border-radius: 8px;
            margin-top: 20px;
            color: #065f46;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon">✅</div>
        <h1>Configuration Saved!</h1>
        <p>Your SensDot device has been configured successfully.</p>
        <p>The device will now restart and connect to your WiFi network.</p>
        <p>It will begin collecting sensor data and sending it to your MQTT broker.</p>
        <div class="countdown">
            Device restarting in <span id="timer">5</span> seconds...
        </div>
    </div>
    
    <script>
        let countdown = 5;
        const timer = document.getElementById('timer');
        setInterval(() => {
            countdown--;
            timer.textContent = countdown;
            if (countdown <= 0) {
                document.querySelector('.countdown').innerHTML = '🔄 Device is restarting...';
            }
        }, 1000);
    </script>
</body>
</html>"""
        
        response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(html)}\r\n\r\n{html}"
        client_socket.send(response.encode())
    
    def _send_error_response(self, client_socket, error_msg):
        """Send error response"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Configuration Error</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }}
        .error {{ color: red; font-size: 18px; }}
    </style>
</head>
<body>
    <div class="error">
        <h1>⚠ Configuration Error</h1>
        <p>{error_msg}</p>
        <a href="/">← Back to configuration</a>
    </div>
</body>
</html>"""
        
        response = f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\nContent-Length: {len(html)}\r\n\r\n{html}"
        client_socket.send(response.encode())
    
    def _send_status_response(self, client_socket):
        """Send device status as JSON"""
        import json
        status = {
            "device_id": self.config_manager.get_device_id(),
            "configured": self.config_manager.is_configured(),
            "config": self.config_manager.get_all_config()
        }
        
        json_data = json.dumps(status)
        response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(json_data)}\r\n\r\n{json_data}"
        client_socket.send(response.encode())
    
    def _restart_device(self):
        """Restart the device after configuration"""
        import time
        time.sleep(3)  # Give time for response to be sent
        print("Restarting device...")
        import machine
        machine.reset()
    
    def stop(self):
        """Stop the configuration server"""
        if self.server_socket:
            self.server_socket.close()
        if self.ap:
            self.ap.active(False)
