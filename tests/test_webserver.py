#!/usr/bin/env python3
"""
SensDot Web Interface Test Server
Simulates the ESP32 device web interface on Windows for testing
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import webbrowser
import threading
import time

class SensDotWebHandler(BaseHTTPRequestHandler):
    """HTTP handler that mimics the ESP32 device web interface"""
    
    def __init__(self, *args, **kwargs):
        # Mock configuration data
        self.mock_config = {
            'wifi': {
                'ssid': '',
                'password': ''
            },
            'mqtt': {
                'broker': '',
                'port': 1883,
                'username': '',
                'password': '',
                'topic': ''
            },
            'ntp': {
                'enable_ntp': True,
                'ntp_server': 'pool.ntp.org',
                'timezone_offset': 0,
                'ntp_sync_interval': 3600,
                'dst_region': 'NONE'
            }
        }
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests - serve the configuration page"""
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Generate the HTML page (similar to ESP32 version)
            html_content = self.generate_config_page()
            self.wfile.write(html_content.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Handle POST requests - process configuration updates"""
        if self.path == '/':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            # Parse form data
            params = parse_qs(post_data)
            
            # Update mock configuration
            if 'ssid' in params:
                self.mock_config['wifi']['ssid'] = params['ssid'][0]
            if 'password' in params:
                self.mock_config['wifi']['password'] = params['password'][0]
            if 'broker' in params:
                self.mock_config['mqtt']['broker'] = params['broker'][0]
            if 'port' in params:
                try:
                    self.mock_config['mqtt']['port'] = int(params['port'][0])
                except ValueError:
                    pass
            if 'username' in params:
                self.mock_config['mqtt']['username'] = params['username'][0]
            if 'mqtt_password' in params:
                self.mock_config['mqtt']['password'] = params['mqtt_password'][0]
            if 'topic' in params:
                self.mock_config['mqtt']['topic'] = params['topic'][0]
            if 'timezone_offset' in params:
                try:
                    self.mock_config['ntp']['timezone_offset'] = float(params['timezone_offset'][0])
                except ValueError:
                    pass
            if 'dst_region' in params:
                self.mock_config['ntp']['dst_region'] = params['dst_region'][0]
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            success_page = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>SensDot - Configuration Saved</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; background: #f0f0f0; }
                    .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                    .success { color: #28a745; text-align: center; }
                    .config-display { background: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 20px; }
                    pre { white-space: pre-wrap; }
                    .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; text-decoration: none; display: inline-block; margin-top: 20px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 class="success">✅ Configuration Saved Successfully!</h1>
                    <p>In a real device, this would restart and connect to your network.</p>
                    
                    <div class="config-display">
                        <h3>Current Configuration:</h3>
                        <pre>{}</pre>
                    </div>
                    
                    <a href="/" class="btn">← Back to Configuration</a>
                </div>
            </body>
            </html>
            """.format(json.dumps(self.mock_config, indent=2))
            
            self.wfile.write(success_page.encode('utf-8'))
    
    def generate_config_page(self):
        """Generate the HTML configuration page"""
        wifi_config = self.mock_config['wifi']
        mqtt_config = self.mock_config['mqtt']
        ntp_config = self.mock_config['ntp']
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SensDot Configuration</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e9ecef;
        }}
        .device-id {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            margin: 15px 0;
            font-family: monospace;
            border-left: 4px solid #007bff;
        }}
        .section {{
            margin-bottom: 25px;
            padding: 20px;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            background: #f8f9fa;
        }}
        .section h3 {{
            margin-top: 0;
            color: #495057;
            border-bottom: 1px solid #dee2e6;
            padding-bottom: 10px;
        }}
        .input-group {{
            margin-bottom: 15px;
        }}
        label {{
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
            color: #495057;
        }}
        input[type="text"], input[type="password"], input[type="number"], select {{
            width: 100%;
            padding: 12px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s;
            box-sizing: border-box;
        }}
        input:focus, select:focus {{
            outline: none;
            border-color: #007bff;
            box-shadow: 0 0 0 3px rgba(0,123,255,0.1);
        }}
        small {{
            display: block;
            margin-top: 5px;
            color: #6c757d;
            font-size: 12px;
        }}
        .btn-group {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e9ecef;
        }}
        .btn {{
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            padding: 15px 30px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s;
            margin: 0 10px;
        }}
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,123,255,0.3);
        }}
        .btn-secondary {{
            background: linear-gradient(135deg, #6c757d, #495057);
        }}
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        .status-connecting {{ background: #ffc107; }}
        .status-connected {{ background: #28a745; }}
        .status-disconnected {{ background: #dc3545; }}
        .advanced-toggle {{
            background: #e9ecef;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            width: 100%;
            margin-bottom: 15px;
            font-weight: 500;
        }}
        .advanced-content {{
            display: block;
        }}
    </style>
    <script>
        function toggleAdvanced() {{
            const content = document.getElementById('advanced-content');
            const button = document.getElementById('advanced-toggle');
            if (content.style.display === 'none') {{
                content.style.display = 'block';
                button.textContent = '▼ Hide Advanced Settings';
            }} else {{
                content.style.display = 'none';
                button.textContent = '▶ Show Advanced Settings';
            }}
        }}
        
        function updateTimezoneFromCity() {{
            const citySelect = document.getElementById('city_timezone');
            const dstSelect = document.getElementById('dst_region');
            
            if (citySelect.value) {{
                const [offset, dst] = citySelect.value.split(',');
                
                // Update DST dropdown
                dstSelect.value = dst;
                
                // Create or update hidden timezone offset field for form submission
                let hiddenOffset = document.getElementById('timezone_offset_hidden');
                if (!hiddenOffset) {{
                    hiddenOffset = document.createElement('input');
                    hiddenOffset.type = 'hidden';
                    hiddenOffset.name = 'timezone_offset';
                    hiddenOffset.id = 'timezone_offset_hidden';
                    citySelect.parentNode.appendChild(hiddenOffset);
                }}
                hiddenOffset.value = offset;
                
                // Visual feedback
                citySelect.style.backgroundColor = '#e8f5e8';
                dstSelect.style.backgroundColor = '#e8f5e8';
                setTimeout(() => {{
                    citySelect.style.backgroundColor = '';
                    dstSelect.style.backgroundColor = '';
                }}, 1000);
            }}
        }}
        
        function validateForm() {{
            const ssid = document.getElementById('ssid').value;
            const broker = document.getElementById('broker').value;
            
            if (!ssid.trim()) {{
                alert('Please enter a WiFi network name (SSID)');
                return false;
            }}
            
            if (!broker.trim()) {{
                alert('Please enter an MQTT broker address');
                return false;
            }}
            
            return true;
        }}
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌐 SensDot Configuration</h1>
            <div class="device-id">
                <strong>Device ID:</strong> TEST-DEVICE-WINDOWS
                <br><small>Status: <span class="status-indicator status-connecting"></span>Configuration Mode</small>
            </div>
        </div>

        <form method="POST" onsubmit="return validateForm()">
            <!-- WiFi Configuration -->
            <div class="section">
                <h3>📶 WiFi Settings</h3>
                <div class="input-group">
                    <label for="ssid">Network Name (SSID) *</label>
                    <input type="text" name="ssid" id="ssid" value="{wifi_config['ssid']}" required>
                    <small>Choose a WiFi network to connect to</small>
                </div>
                <div class="input-group">
                    <label for="password">Password</label>
                    <input type="password" name="password" id="password" value="{wifi_config['password']}">
                    <small>Leave empty if network is open</small>
                </div>
            </div>

            <!-- MQTT Configuration -->
            <div class="section">
                <h3>📡 MQTT Settings</h3>
                <div class="input-group">
                    <label for="broker">MQTT Broker Address *</label>
                    <input type="text" name="broker" id="broker" value="{mqtt_config['broker']}" required>
                    <small>Example: mqtt.home.local or 192.168.1.100</small>
                </div>
                <div class="input-group">
                    <label for="port">Port</label>
                    <input type="number" name="port" id="port" value="{mqtt_config['port']}" min="1" max="65535">
                    <small>Default: 1883 (standard), 8883 (SSL)</small>
                </div>
                <div class="input-group">
                    <label for="topic">Topic Prefix</label>
                    <input type="text" name="topic" id="topic" value="{mqtt_config['topic']}">
                    <small>Example: sensors/kitchen or home/sensdot</small>
                </div>
                <div class="input-group">
                    <label for="username">Username</label>
                    <input type="text" name="username" id="username" value="{mqtt_config['username']}">
                    <small>Leave empty if broker doesn't require authentication</small>
                </div>
                <div class="input-group">
                    <label for="mqtt_password">Password</label>
                    <input type="password" name="mqtt_password" id="mqtt_password" value="{mqtt_config['password']}">
                </div>
            </div>

            <!-- Advanced Settings -->
            <button type="button" class="advanced-toggle" id="advanced-toggle" onclick="toggleAdvanced()">
                ▼ Hide Advanced Settings
            </button>
            
            <div id="advanced-content" class="advanced-content">
                <div class="section">
                    <h3>⏰ Time & Timezone Settings</h3>
                    <div class="input-group">
                        <label for="city_timezone">Select Your City/Region</label>
                        <select name="city_timezone" id="city_timezone" onchange="updateTimezoneFromCity()">
                            <option value="">Choose a city...</option>
                            <optgroup label="UTC/GMT">
                                <option value="0,NONE">UTC+0: Coordinated Universal Time</option>
                                <option value="0,EU">UTC+0: London, Dublin</option>
                                <option value="0,AFRICA">UTC+0: Lisbon, Casablanca</option>
                            </optgroup>
                            <optgroup label="Europe">
                                <option value="1,EU">UTC+1: Paris, Berlin, Rome, Stockholm</option>
                                <option value="1,EU">UTC+1: Amsterdam, Brussels, Copenhagen</option>
                                <option value="1,EU">UTC+1: Prague, Vienna, Warsaw</option>
                                <option value="2,EU">UTC+2: Athens, Helsinki, Istanbul</option>
                                <option value="2,EU">UTC+2: Bucharest, Sofia, Tallinn</option>
                                <option value="3,NONE">UTC+3: Moscow, St. Petersburg</option>
                            </optgroup>
                            <optgroup label="North America">
                                <option value="-5,US">UTC-5: New York, Toronto, Montreal</option>
                                <option value="-5,US">UTC-5: Miami, Atlanta, Boston</option>
                                <option value="-6,US">UTC-6: Chicago, Dallas, Mexico City</option>
                                <option value="-7,US">UTC-7: Denver, Phoenix, Salt Lake City</option>
                                <option value="-8,US">UTC-8: Los Angeles, San Francisco, Seattle</option>
                                <option value="-9,US">UTC-9: Anchorage</option>
                                <option value="-10,NONE">UTC-10: Honolulu</option>
                            </optgroup>
                            <optgroup label="Asia">
                                <option value="9,NONE">UTC+9: Tokyo, Seoul, Osaka</option>
                                <option value="8,NONE">UTC+8: Beijing, Shanghai, Hong Kong</option>
                                <option value="8,NONE">UTC+8: Singapore, Kuala Lumpur</option>
                                <option value="7,NONE">UTC+7: Bangkok, Jakarta, Hanoi</option>
                                <option value="5.5,NONE">UTC+5.5: Mumbai, New Delhi, Kolkata</option>
                                <option value="4,NONE">UTC+4: Dubai, Abu Dhabi</option>
                                <option value="3.5,ME">UTC+3.5: Tehran</option>
                            </optgroup>
                            <optgroup label="Australia & Pacific">
                                <option value="10,AU">UTC+10: Sydney, Melbourne, Brisbane</option>
                                <option value="9.5,AU">UTC+9.5: Adelaide</option>
                                <option value="8,NONE">UTC+8: Perth</option>
                                <option value="12,AU">UTC+12: Auckland</option>
                            </optgroup>
                            <optgroup label="South America">
                                <option value="-3,SA">UTC-3: Buenos Aires, São Paulo</option>
                                <option value="-4,SA">UTC-4: Santiago</option>
                                <option value="-5,NONE">UTC-5: Lima, Bogotá</option>
                            </optgroup>
                            <optgroup label="Africa">
                                <option value="2,NONE">UTC+2: Cairo, Johannesburg</option>
                                <option value="1,NONE">UTC+1: Lagos, Kinshasa</option>
                                <option value="3,NONE">UTC+3: Nairobi, Addis Ababa</option>
                            </optgroup>
                        </select>
                        <small style="color: #666; font-size: 0.85em;">Choose your city for automatic timezone and DST settings</small>
                    </div>
                    <div class="input-group">
                        <label for="dst_region">Daylight Saving Time</label>
                        <select name="dst_region" id="dst_region">
                            <option value="NONE" {'selected' if ntp_config.get('dst_region', 'NONE') == 'NONE' else ''}>No Daylight Saving Time</option>
                            <option value="EU" {'selected' if ntp_config.get('dst_region', 'NONE') == 'EU' else ''}>Europe (Mar-Oct)</option>
                            <option value="US" {'selected' if ntp_config.get('dst_region', 'NONE') == 'US' else ''}>USA/Canada (Mar-Nov)</option>
                            <option value="AU" {'selected' if ntp_config.get('dst_region', 'NONE') == 'AU' else ''}>Australia (Oct-Apr)</option>
                            <option value="SA" {'selected' if ntp_config.get('dst_region', 'NONE') == 'SA' else ''}>South America (Oct-Mar)</option>
                            <option value="ME" {'selected' if ntp_config.get('dst_region', 'NONE') == 'ME' else ''}>Middle East (Mar-Oct)</option>
                            <option value="AFRICA" {'selected' if ntp_config.get('dst_region', 'NONE') == 'AFRICA' else ''}>Africa (Mar-Oct)</option>
                        </select>
                        <small style="color: #666; font-size: 0.85em;">Automatically adjusts time for summer/winter</small>
                    </div>
                </div>
            </div>

            <div class="btn-group">
                <button type="submit" class="btn">💾 Save Configuration</button>
                <button type="button" class="btn btn-secondary" onclick="location.reload()">🔄 Reset Form</button>
            </div>
        </form>
    </div>
</body>
</html>"""

    def log_message(self, format, *args):
        """Override to reduce console noise"""
        pass

def open_browser_delayed():
    """Open browser after a short delay"""
    time.sleep(1)
    webbrowser.open('http://localhost:8080')

def main():
    """Start the test web server"""
    server_address = ('localhost', 8080)
    httpd = HTTPServer(server_address, SensDotWebHandler)
    
    print("🌐 SensDot Web Interface Test Server")
    print("=" * 50)
    print(f"Server running at: http://localhost:8080")
    print("This simulates the ESP32 device configuration interface")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 50)
    
    # Open browser in background thread
    browser_thread = threading.Thread(target=open_browser_delayed)
    browser_thread.daemon = True
    browser_thread.start()
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        httpd.server_close()

if __name__ == '__main__':
    main()
