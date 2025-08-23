# simple_wifi_config.py
# Enhanced WiFi configuration server with password visibility toggles

import network
import socket
import time
import machine
from config_manager import ConfigManager

def start_simple_ap():
    """Start a simple WiFi AP with enhanced web server"""
    
    # Initialize config manager
    config = ConfigManager()
    
    # Create AP
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    
    # Get device ID for AP name
    device_id = machine.unique_id()
    ap_name = f"SensDot-{device_id[-1]:02x}{device_id[-2]:02x}"
    
    # Configure as open network
    ap.config(essid=ap_name, authmode=0)
    
    print(f"AP started: {ap_name}")
    print(f"IP: {ap.ifconfig()[0]}")
    
    # Simple web server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 80))
    s.listen(1)
    
    print("Web server listening on port 80")
    
    while True:
        try:
            conn, addr = s.accept()
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
                handle_config_post(request, conn, config)
            # Handle common captive portal detection URLs
            elif method == 'GET' and (
                path in ['/generate_204', '/hotspot-detect.html', '/connecttest.txt', 
                        '/redirect', '/success.txt', '/ncsi.txt'] or
                path.startswith('/fwlink') or  # Microsoft
                'kindle-wifi' in path or       # Amazon
                'library/test/success.html' in path  # Apple alternative
            ):
                print(f"Captive portal probe detected: {path}")
                send_captive_redirect(conn)
            # Handle favicon and other assets
            elif method == 'GET' and (path == '/favicon.ico' or path.endswith('.ico')):
                send_404(conn)
            # Send configuration form for root and other paths
            else:
                send_config_form(conn, config)
            
            conn.close()
            
        except Exception as e:
            print(f"Error: {e}")
            try:
                conn.close()
            except:
                pass

def handle_config_post(request, conn, config):
    """Handle configuration form submission"""
    try:
        # Parse form data
        body_start = request.find('\r\n\r\n')
        if body_start == -1:
            send_error_response(conn)
            return
        
        body = request[body_start + 4:]
        form_data = parse_form_data(body)
        
        # Save configuration
        if 'wifi_ssid' in form_data and 'mqtt_broker' in form_data:
            config.set_wifi_config(form_data.get('wifi_ssid'), form_data.get('wifi_password', ''))
            config.set_mqtt_config(
                form_data.get('mqtt_broker'),
                int(form_data.get('mqtt_port', 1883)),
                form_data.get('mqtt_username', ''),
                form_data.get('mqtt_password', ''),
                form_data.get('mqtt_topic', 'sensdot')
            )
            send_success_response(conn)
            
            # Schedule restart after sending response
            print("Configuration saved. Restarting in 5 seconds...")
            import time
            time.sleep(5)
            import machine
            machine.reset()
        else:
            send_error_response(conn)
            
    except Exception as e:
        print(f"Config error: {e}")
        send_error_response(conn)

def parse_form_data(body):
    """Parse URL-encoded form data"""
    data = {}
    pairs = body.split('&')
    for pair in pairs:
        if '=' in pair:
            key, value = pair.split('=', 1)
            # Basic URL decoding
            value = value.replace('+', ' ').replace('%40', '@').replace('%2F', '/')
            data[key] = value
    return data

def send_config_form(conn, config):
    """Send configuration form with password visibility toggles"""
    current_config = config.get_all_config()
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>SensDot Configuration</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }}
        .container {{ max-width: 500px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }}
        h1 {{ color: #333; text-align: center; }}
        .form-group {{ margin-bottom: 15px; }}
        label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
        input {{ width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }}
        .password-container {{ display: flex; gap: 5px; align-items: stretch; }}
        .password-container input {{ flex: 1; min-width: 0; }}
        .eye-button {{ background: #f8f9fa; border: 1px solid #ddd; cursor: pointer; padding: 8px 8px; font-size: 10px; color: #666; border-radius: 3px; flex-shrink: 0; width: 45px; }}
        .eye-button:hover {{ background: #e9ecef; color: #333; }}
        button {{ width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }}
        button:hover {{ background: #0056b3; }}
        .device-info {{ background: #e9ecef; padding: 10px; border-radius: 4px; margin-bottom: 20px; }}
        .captive-notice {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 10px; border-radius: 4px; margin-bottom: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="captive-notice">
            <strong>SensDot Configuration Required</strong><br>
            Please configure your device to continue
        </div>
        
        <h1>[CONFIG] SensDot Configuration</h1>
        <div class="device-info">
            <strong>Device ID:</strong> {config.get_device_id()}<br>
            <strong>Status:</strong> Configuration Mode<br>
            <strong>IP Address:</strong> 192.168.4.1
        </div>
        
        <form method="POST" action="/">
            <div class="form-group">
                <label>WiFi Network Name (SSID):</label>
                <input type="text" name="wifi_ssid" value="{current_config.get('wifi_ssid', '')}" required>
            </div>
            
            <div class="form-group">
                <label>WiFi Password:</label>
                <div class="password-container">
                    <input type="password" id="wifi_password" name="wifi_password" value="{current_config.get('wifi_password', '')}">
                    <button type="button" class="eye-button" onclick="togglePassword('wifi_password', this)">SHOW</button>
                </div>
            </div>
            
            <div class="form-group">
                <label>MQTT Broker IP/Hostname:</label>
                <input type="text" name="mqtt_broker" value="{current_config.get('mqtt_broker', '')}" required>
            </div>
            
            <div class="form-group">
                <label>MQTT Port:</label>
                <input type="number" name="mqtt_port" value="{current_config.get('mqtt_port', 1883)}">
            </div>
            
            <div class="form-group">
                <label>MQTT Username (optional):</label>
                <input type="text" name="mqtt_username" value="{current_config.get('mqtt_username', '')}">
            </div>
            
            <div class="form-group">
                <label>MQTT Password (optional):</label>
                <div class="password-container">
                    <input type="password" id="mqtt_password" name="mqtt_password" value="{current_config.get('mqtt_password', '')}">
                    <button type="button" class="eye-button" onclick="togglePassword('mqtt_password', this)">SHOW</button>
                </div>
            </div>
            
            <div class="form-group">
                <label>MQTT Topic:</label>
                <input type="text" name="mqtt_topic" value="{current_config.get('mqtt_topic', 'sensdot')}">
            </div>
            
            <button type="submit">[SAVE] Save Configuration</button>
        </form>
    </div>
    
    <script>
        function togglePassword(fieldId, button) {{
            const field = document.getElementById(fieldId);
            if (field.type === 'password') {{
                field.type = 'text';
                button.innerHTML = 'HIDE';
            }} else {{
                field.type = 'password';
                button.innerHTML = 'SHOW';
            }}
        }}
    </script>
</body>
</html>"""
    
    response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(html)}\r\n\r\n{html}"
    conn.send(response.encode('utf-8'))

def send_success_response(conn):
    """Send success response"""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Configuration Saved</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
        .container { max-width: 500px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; text-align: center; }
        h1 { color: #28a745; }
        .message { margin: 20px 0; font-size: 18px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>[SUCCESS] Configuration Saved!</h1>
        <div class="message">
            Your SensDot device has been configured successfully.<br>
            The device will restart and connect to your WiFi network.
        </div>
        <p>You can now disconnect from this WiFi network.</p>
    </div>
    <script>
        setTimeout(function() {
            document.body.innerHTML = '<div class="container"><h1>[RESTART] Restarting...</h1><p>Device is restarting with new configuration.</p></div>';
        }, 3000);
    </script>
</body>
</html>"""
    
    response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(html)}\r\n\r\n{html}"
    conn.send(response.encode('utf-8'))

def send_error_response(conn):
    """Send error response"""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Configuration Error</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
        .container { max-width: 500px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; text-align: center; }
        h1 { color: #dc3545; }
    </style>
</head>
<body>
    <div class="container">
        <h1>[ERROR] Configuration Error</h1>
        <p>Please fill in all required fields and try again.</p>
        <a href="/">← Go Back</a>
    </div>
</body>
</html>"""
    
    response = f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\nContent-Length: {len(html)}\r\n\r\n{html}"
    conn.send(response.encode('utf-8'))

def send_captive_redirect(conn):
    """Send captive portal redirect response"""
    # Redirect to configuration page
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

def send_404(conn):
    """Send 404 response for missing resources"""
    response = "HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n404 Not Found"
    conn.send(response.encode('utf-8'))
    conn.close()

if __name__ == "__main__":
    start_simple_ap()
