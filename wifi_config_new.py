# wifi_config.py
# Enhanced WiFi configuration server with password visibility toggles and captive portal
# Consolidated version - replaces all other wifi_config files

import network
import socket
import time
import machine
from config_manager import ConfigManager

class WiFiConfigServer:
    """Enhanced WiFi configuration server with modern UI features"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.ap = None
        self.server_socket = None
        
    def start_config_server(self):
        """Start WiFi AP and configuration web server"""
        print("Starting WiFi configuration server...")
        
        # Create AP
        self.ap = network.WLAN(network.AP_IF)
        self.ap.active(True)
        
        # Get device ID for AP name
        device_id = machine.unique_id()
        ap_name = f"SensDot-{device_id[-1]:02x}{device_id[-2]:02x}"
        
        # Configure as open network for easy access
        self.ap.config(essid=ap_name, authmode=0)
        
        print(f"WiFi AP started: {ap_name}")
        print(f"Connect to this network and go to: http://192.168.4.1")
        print(f"AP IP: {self.ap.ifconfig()[0]}")
        
        # Start web server
        self._start_web_server()
        
    def _start_web_server(self):
        """Start the web server for configuration"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', 80))
        self.server_socket.listen(1)
        
        print("Configuration web server started on port 80")
        
        while True:
            try:
                conn, addr = self.server_socket.accept()
                print(f"Connection from {addr}")
                
                # Read request
                request = conn.recv(1024).decode('utf-8')
                print(f"Request: {request[:100]}...")
                
                # Extract request method and path more carefully
                lines = request.split('\n')
                request_line = lines[0].strip() if lines else ""
                
                # Parse method and path
                method = ""
                path = "/"
                if ' ' in request_line:
                    parts = request_line.split(' ')
                    if len(parts) >= 2:
                        method = parts[0]
                        path = parts[1]
                
                print(f"Method: {method}, Path: {path}")
                
                # Handle POST requests (form submission)
                if method == 'POST':
                    self._handle_config_post(request, conn)
                # Handle common captive portal detection URLs
                elif method == 'GET' and (
                    path in ['/generate_204', '/hotspot-detect.html', '/connecttest.txt', 
                            '/redirect', '/success.txt', '/ncsi.txt'] or
                    path.startswith('/fwlink') or  # Microsoft
                    'kindle-wifi' in path or       # Amazon
                    'library/test/success.html' in path  # Apple alternative
                ):
                    print(f"Captive portal probe detected: {path}")
                    self._send_captive_redirect(conn)
                # Handle favicon and other assets
                elif method == 'GET' and (path == '/favicon.ico' or path.endswith('.ico')):
                    self._send_404(conn)
                # Send configuration form for root and other paths
                else:
                    self._send_config_form(conn)
                    
            except Exception as e:
                print(f"Server error: {e}")
                try:
                    conn.close()
                except:
                    pass
                continue

    def _handle_config_post(self, request, conn):
        """Handle configuration form submission"""
        try:
            # Extract form data from POST body
            body_start = request.find('\r\n\r\n')
            if body_start == -1:
                body_start = request.find('\n\n')
            
            if body_start != -1:
                body = request[body_start + 4:]
                print(f"Form data: {body}")
                
                # Parse form data
                params = {}
                for pair in body.split('&'):
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        # URL decode
                        value = value.replace('+', ' ')
                        value = value.replace('%40', '@')
                        value = value.replace('%3A', ':')
                        value = value.replace('%2F', '/')
                        params[key] = value
                
                # Validate and save configuration
                if 'wifi_ssid' in params and 'mqtt_broker' in params:
                    print("Saving configuration...")
                    
                    # Save WiFi config
                    self.config_manager.set_wifi_config(
                        params.get('wifi_ssid', ''),
                        params.get('wifi_password', '')
                    )
                    
                    # Save MQTT config
                    self.config_manager.set_mqtt_config(
                        params.get('mqtt_broker', ''),
                        int(params.get('mqtt_port', 1883)),
                        params.get('mqtt_topic', 'sensdot'),
                        params.get('mqtt_username', ''),
                        params.get('mqtt_password', '')
                    )
                    
                    # Save advanced config
                    self.config_manager.set_advanced_config(
                        int(params.get('sleep_interval', 60)),
                        int(params.get('sensor_interval', 30)),
                        params.get('debug_mode') == 'on'
                    )
                    
                    # Send success response
                    self._send_success_response(conn)
                    
                    # Close server and restart device
                    print("Configuration saved, restarting device...")
                    time.sleep(2)
                    machine.reset()
                else:
                    self._send_error_response(conn, "Missing required fields")
            else:
                self._send_error_response(conn, "Invalid form data")
                
        except Exception as e:
            print(f"Config POST error: {e}")
            self._send_error_response(conn, str(e))

    def _send_config_form(self, conn):
        """Send the enhanced configuration form with password toggles"""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SensDot Configuration</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 500px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            text-align: center;
            padding: 30px 20px;
        }
        
        .header h1 {
            font-size: 28px;
            margin-bottom: 8px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 14px;
        }
        
        .form-container {
            padding: 30px;
        }
        
        .section {
            margin-bottom: 25px;
        }
        
        .section-title {
            color: #4CAF50;
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid #e8f5e8;
        }
        
        .input-group {
            margin-bottom: 15px;
        }
        
        .input-group label {
            display: block;
            margin-bottom: 6px;
            font-weight: 500;
            color: #555;
        }
        
        .password-container {
            position: relative;
            display: flex;
            align-items: center;
        }
        
        .password-container input {
            flex: 1;
            margin-right: 8px;
        }
        
        .toggle-btn {
            background: #f0f0f0;
            border: 1px solid #ddd;
            border-radius: 6px;
            width: 36px;
            height: 36px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            color: #666;
            transition: all 0.2s;
            flex-shrink: 0;
        }
        
        .toggle-btn:hover {
            background: #e0e0e0;
            color: #333;
        }
        
        input[type="text"], input[type="password"], input[type="number"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        input[type="text"]:focus, input[type="password"]:focus, input[type="number"]:focus {
            outline: none;
            border-color: #4CAF50;
        }
        
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        input[type="checkbox"] {
            width: 18px;
            height: 18px;
            accent-color: #4CAF50;
        }
        
        .submit-btn {
            width: 100%;
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            border: none;
            padding: 15px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .submit-btn:hover {
            transform: translateY(-2px);
        }
        
        .info {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            font-size: 14px;
            color: #1976d2;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔧 SensDot Config</h1>
            <p>Configure your IoT device</p>
        </div>
        
        <div class="form-container">
            <form method="POST" action="/">
                <div class="section">
                    <div class="section-title">📶 WiFi Settings</div>
                    <div class="input-group">
                        <label for="wifi_ssid">Network Name (SSID)</label>
                        <input type="text" name="wifi_ssid" id="wifi_ssid" required>
                    </div>
                    <div class="input-group">
                        <label for="wifi_password">Password</label>
                        <div class="password-container">
                            <input type="password" name="wifi_password" id="wifi_password">
                            <button type="button" class="toggle-btn" onclick="togglePassword('wifi_password', this)">👁️</button>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">📡 MQTT Settings</div>
                    <div class="input-group">
                        <label for="mqtt_broker">Broker Address</label>
                        <input type="text" name="mqtt_broker" id="mqtt_broker" required>
                    </div>
                    <div class="input-group">
                        <label for="mqtt_port">Port</label>
                        <input type="number" name="mqtt_port" id="mqtt_port" value="1883">
                    </div>
                    <div class="input-group">
                        <label for="mqtt_topic">Topic Prefix</label>
                        <input type="text" name="mqtt_topic" id="mqtt_topic" value="sensdot">
                    </div>
                    <div class="input-group">
                        <label for="mqtt_username">Username (optional)</label>
                        <input type="text" name="mqtt_username" id="mqtt_username">
                    </div>
                    <div class="input-group">
                        <label for="mqtt_password">Password (optional)</label>
                        <div class="password-container">
                            <input type="password" name="mqtt_password" id="mqtt_password">
                            <button type="button" class="toggle-btn" onclick="togglePassword('mqtt_password', this)">👁️</button>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">⚙️ Advanced Settings</div>
                    <div class="input-group">
                        <label for="sleep_interval">Sleep Interval (seconds)</label>
                        <input type="number" name="sleep_interval" id="sleep_interval" value="60" min="10">
                    </div>
                    <div class="input-group">
                        <label for="sensor_interval">Sensor Reading Interval (seconds)</label>
                        <input type="number" name="sensor_interval" id="sensor_interval" value="30" min="5">
                    </div>
                    <div class="input-group">
                        <div class="checkbox-group">
                            <input type="checkbox" name="debug_mode" id="debug_mode">
                            <label for="debug_mode">Enable Debug Mode</label>
                        </div>
                    </div>
                </div>
                
                <button type="submit" class="submit-btn">💾 Save Configuration</button>
            </form>
            
            <div class="info">
                <strong>ℹ️ Instructions:</strong><br>
                1. Enter your WiFi network details<br>
                2. Configure MQTT broker settings<br>
                3. Adjust timing intervals as needed<br>
                4. Click Save to restart the device
            </div>
        </div>
    </div>
    
    <script>
        function togglePassword(inputId, button) {
            const input = document.getElementById(inputId);
            if (input.type === 'password') {
                input.type = 'text';
                button.textContent = '🙈';
            } else {
                input.type = 'password';
                button.textContent = '👁️';
            }
        }
    </script>
</body>
</html>"""
        
        response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(html)}\r\n\r\n{html}"
        conn.send(response.encode('utf-8'))
        conn.close()

    def _send_success_response(self, conn):
        """Send success response after configuration save"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configuration Saved</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f8ff; }
        .success { background: #d4edda; border: 1px solid #c3e6cb; border-radius: 8px; padding: 30px; color: #155724; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #4CAF50; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 20px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="success">
        <h1>✅ Configuration Saved!</h1>
        <p>Your SensDot device is restarting...</p>
        <div class="spinner"></div>
        <p>The device will now connect to your WiFi network and start operating.</p>
    </div>
</body>
</html>"""
        
        response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n{html}"
        conn.send(response.encode('utf-8'))
        conn.close()

    def _send_error_response(self, conn, error_msg):
        """Send error response"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Configuration Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #fff5f5; }}
        .error {{ background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 8px; padding: 30px; color: #721c24; }}
    </style>
</head>
<body>
    <div class="error">
        <h1>❌ Configuration Error</h1>
        <p>{error_msg}</p>
        <p><a href="/">← Go Back</a></p>
    </div>
</body>
</html>"""
        
        response = f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n{html}"
        conn.send(response.encode('utf-8'))
        conn.close()

    def _send_captive_redirect(self, conn):
        """Send captive portal redirect response"""
        redirect_html = """<!DOCTYPE html>
<html>
<head>
    <title>SensDot Configuration</title>
    <meta http-equiv="refresh" content="0; url=http://192.168.4.1/">
</head>
<body>
    <p>Redirecting to SensDot configuration...</p>
    <p>If not redirected automatically, <a href="http://192.168.4.1/">click here</a></p>
</body>
</html>"""
        
        response = f"HTTP/1.1 302 Found\r\nLocation: http://192.168.4.1/\r\nContent-Type: text/html\r\nContent-Length: {len(redirect_html)}\r\n\r\n{redirect_html}"
        conn.send(response.encode('utf-8'))

    def _send_404(self, conn):
        """Send 404 response for missing resources"""
        response = "HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n404 Not Found"
        conn.send(response.encode('utf-8'))
        conn.close()


# Standalone function for backward compatibility
def start_simple_ap():
    """Start a simple WiFi AP with enhanced web server (standalone mode)"""
    config = ConfigManager()
    server = WiFiConfigServer(config)
    server.start_config_server()


if __name__ == "__main__":
    start_simple_ap()
