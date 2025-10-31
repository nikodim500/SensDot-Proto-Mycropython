"""Streaming, memory-safe WiFi configuration portal for SensDot (ESP32-C3).

Features:
- Rich UI streamed in small chunks to avoid MemoryError on MicroPython
- AJAX /scan endpoint to refresh SSID list without page reload
- MQTT layout: broker+port on one row; username and password rows below
"""

import network, socket, time, machine, gc
from config_manager import ConfigManager


class WiFiConfigServer:
    def __init__(self, config_manager: ConfigManager, logger=None):
        self.config_manager = config_manager
        self.logger = logger
        self.ap = None
        self.sock = None

    # ---------- Logging ----------
    def _log(self, level, msg):
        if self.logger:
            fn = getattr(self.logger, level, self.logger.info)
            fn(msg)
        else:
            print("[{}] {}".format(level, msg))

    # ---------- Public ----------
    def start_config_server(self):
        self._log('info', 'Starting WiFi configuration AP...')
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        dev_id = machine.unique_id()
        ap_name = "SensDot-%02x%02x" % (dev_id[-1], dev_id[-2])
        try:
            ap.config(essid=ap_name, authmode=0)  # open AP
        except Exception as e:
            self._log('warn', 'AP config warn: {}'.format(e))
        self.ap = ap
        self._log('info', 'AP started: {} (http://192.168.4.1)'.format(ap_name))
        self._start_web_server()

    # ---------- HTTP Core ----------
    def _start_web_server(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        gc.collect()
        addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(2)
        self.sock = s
        self._log('info', 'HTTP server listening on 0.0.0.0:80')
        while True:
            try:
                conn, _ = s.accept()
                conn.settimeout(5)
                req = conn.recv(1024)
                if not req:
                    conn.close()
                    continue
                first = req.split(b"\r\n", 1)[0]
                parts = first.decode('utf-8', 'ignore').split()
                method = parts[0] if parts else 'GET'
                path = parts[1] if len(parts) > 1 else '/'
                if method == 'POST':
                    # Read body according to Content-Length
                    headers_body = req.split(b"\r\n\r\n", 1)
                    body = b''
                    if len(headers_body) == 2:
                        header_block, body = headers_body
                        for line in header_block.split(b"\r\n"):
                            if line.lower().startswith(b'content-length'):
                                try:
                                    need = int(line.split(b":", 1)[1].strip())
                                except:
                                    need = 0
                                while len(body) < need:
                                    more = conn.recv(need - len(body))
                                    if not more:
                                        break
                                    body += more
                                break
                    form = self._parse_urlencoded(body.decode('utf-8', 'ignore'))
                    self._handle_config_post(conn, form)
                else:
                    # Log method and path for diagnostics
                    try:
                        self._log('info', 'HTTP {} {}'.format(method, path))
                    except:
                        pass
                    if path == '/' or path.startswith('/index'):
                        try:
                            conn.settimeout(20)
                        except:
                            pass
                        self._send_config_form(conn)
                    elif path.startswith('/scan'):
                        try:
                            conn.settimeout(10)
                        except:
                            pass
                        self._send_scan_list(conn)
                    else:
                        self._send_404(conn)
            except Exception as e:
                if 'ETIMEDOUT' not in str(e):
                    self._log('warn', 'HTTP error: {}'.format(e))
                try:
                    conn.close()
                except:
                    pass
            gc.collect()

    # ---------- Helpers ----------
    def _parse_urlencoded(self, data):
        out = {}
        for pair in data.split('&'):
            if not pair:
                continue
            if '=' in pair:
                k, v = pair.split('=', 1)
            else:
                k, v = pair, ''
            out[self._urldecode(k)] = self._urldecode(v)
        return out

    def _urldecode(self, s):
        s = s.replace('+', ' ')
        res = ''
        i = 0
        L = len(s)
        while i < L:
            c = s[i]
            if c == '%' and i + 2 < L:
                try:
                    res += chr(int(s[i+1:i+3], 16))
                    i += 3
                    continue
                except:
                    pass
            res += c
            i += 1
        return res

    def _to_int(self, v, d):
        try:
            return int(v)
        except:
            return d

    def _to_float(self, v, d):
        try:
            return float(v)
        except:
            return d

    # ---------- POST ----------
    def _handle_config_post(self, conn, form):
        try:
            wifi_ssid = form.get('wifi_ssid', '')[:64]
            wifi_password = form.get('wifi_password', '')[:64]
            broker = form.get('mqtt_broker', '')[:64]
            port = self._to_int(form.get('mqtt_port', '1883'), 1883)
            mqtt_user = form.get('mqtt_username', '')[:64]
            mqtt_pass = form.get('mqtt_password', '')[:64]

            device_name = form.get('device_name', '')[:40]
            raw_name = form.get('mqtt_name', '')[:40]
            def okch(ch):
                o = ord(ch)
                return (48 <= o <= 57) or (65 <= o <= 90) or (97 <= o <= 122) or (ch == '_') or (ch == '-')
            mqtt_name = ''.join([c for c in raw_name if okch(c)])

            sleep_interval = self._to_int(form.get('sleep_interval', '60'), 60)
            sensor_interval = self._to_int(form.get('sensor_interval', '30'), 30)
            mqtt_discovery = 'mqtt_discovery' in form

            enable_ntp = form.get('enable_ntp', 'on') == 'on'
            ntp_server = form.get('ntp_server', 'pool.ntp.org')[:64]
            tz_off = self._to_float(form.get('timezone_offset', '0'), 0.0)
            dst_region = form.get('dst_region', 'NONE')[:10]
            sync_interval = self._to_int(form.get('ntp_sync_interval', '3600'), 3600)

            if wifi_ssid:
                self.config_manager.set_wifi_config(wifi_ssid, wifi_password)
            if broker:
                self.config_manager.set_mqtt_config(broker, port, mqtt_user, mqtt_pass, '')
            self.config_manager.set_device_names(device_name, mqtt_name)
            self.config_manager.set_advanced_config(sleep_interval, sensor_interval, False, mqtt_discovery)
            self.config_manager.set_ntp_config(enable_ntp, ntp_server, tz_off, dst_region, sync_interval)

            self._send_success_response(conn)
            self._log('info', 'Configuration saved; rebooting in 2s...')
            try:
                time.sleep(2)
                machine.reset()
            except:
                pass
        except Exception as e:
            self._log('error', 'POST failed: {}'.format(e))
            self._send_error_response(conn, 'Invalid form / internal error')

    # ---------- Streaming Page ----------
    def _send_config_form(self, conn):
        try:
            names = self.config_manager.get_device_names()
            wifi = self.config_manager.get_wifi_config()
            mqtt = self.config_manager.get_mqtt_config()
            adv = self.config_manager.get_advanced_config()
            ntp = self.config_manager.get_ntp_config()
        except Exception as e:
            self._log('warn', 'Config read issue: {}'.format(e))
            names = {'device_name': '', 'mqtt_name': ''}
            wifi = {'ssid': '', 'password': ''}
            mqtt = {'broker': '', 'port': 1883, 'username': '', 'password': '', 'topic': ''}
            adv = {'sleep_interval': 60, 'sensor_interval': 30, 'mqtt_discovery': True, 'debug_mode': False}
            ntp = {'enable_ntp': True, 'ntp_server': 'pool.ntp.org', 'timezone_offset': 0, 'dst_region': 'NONE', 'ntp_sync_interval': 3600}

        def S(chunk):
            for _ in range(3):
                try:
                    conn.send(chunk)
                    return
                except Exception as e:
                    es = str(e)
                    # transient or client disconnects
                    if ('ETIMEDOUT' in es) or ('EAGAIN' in es) or ('110' in es) or ('116' in es):
                        try:
                            time.sleep(0.05)
                        except:
                            pass
                        continue
                    if ('ECONNRESET' in es) or ('EPIPE' in es) or ('104' in es) or ('32' in es):
                        # client closed connection; stop sending silently
                        return
                    raise e

        # headers
        S(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n")
        # head
        S(b"<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>")
        S(b"<title>SensDot Config</title><style>body{font-family:Arial;margin:0;padding:0;background:#eef;}h1{margin:0;padding:16px;background:#4a67d6;color:#fff;font-size:20px}section{background:#fff;margin:12px;padding:12px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.1)}label{font-weight:600;font-size:13px;display:block;margin:6px 0 2px}input,select{width:100%;padding:8px;border:1px solid #ccc;border-radius:6px;box-sizing:border-box;font-size:13px}small{color:#555;font-size:11px}button.submit{margin:16px 12px 32px;width:calc(100% - 24px);padding:14px;background:#4a67d6;color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:600}button.submit:active{opacity:.8}.row{display:flex;gap:8px}.")
        S(b"row>*{flex:1}.adv-toggle{background:#f0f0f7;padding:10px 14px;border:none;width:100%;text-align:left;font-weight:600;border-radius:6px;margin:4px 0;}.hidden{display:none}.badge{display:inline-block;background:#4a67d6;color:#fff;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:4px}.pwrow,.ssidrow{display:flex;gap:8px;align-items:center}.pwrow input,.ssidrow input{flex:1}.btn-sm{padding:7px 10px;border:1px solid #ccc;background:#fafafa;border-radius:6px}.ssidbox{position:relative}.sugg{position:absolute;left:0;right:0;border:1px solid #cbd3ff;background:#fff;box-shadow:0 2px 6px rgba(0,0,0,.15);max-height:180px;overflow:auto;margin-top:4px;border-radius:6px;z-index:999}.sugg .it{padding:6px 8px;cursor:pointer}.sugg .it:hover{background:#eef}</style>")
        S(b"<script>function g(id){return document.getElementById(id);}function tAdv(){var a=g('adv');a.classList.toggle('hidden');g('adv_btn').innerHTML=a.classList.contains('hidden')?'Show Advanced >':'Hide Advanced v';}")
        S(b"function vMqttName(inp){var v=inp.value;var ok=/^[a-zA-Z0-9_-]*$/.test(v);var e=g('mqtt_err');if(!ok){e.style.display='block';inp.style.borderColor='#e33';g('save').disabled=true;}else{e.style.display='none';inp.style.borderColor='#4a67d6';g('save').disabled=false;}}")
        S(b"function tp(id,btn){var e=g(id);if(!e)return; if(e.type==='password'){e.type='text';btn.innerHTML='Hide'}else{e.type='password';btn.innerHTML='Show'}}")
        S(b"function esc(t){return (t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;');}")
        S(b"function tzPreset(sel){try{var val=(sel&&sel.value)||'';var p=val.split('|');if(p.length>=2){var off=p[0];var reg=p[1];var o=document.getElementById('tz_off');if(o){o.value=off;}var d=document.getElementById('dst_region');if(d){for(var i=0;i<d.options.length;i++){if(d.options[i].value===reg){d.selectedIndex=i;break;}}}}}catch(e){}}")
        S(b"function buildSugg(){var dl=g('ssid_list');var c=g('ssid_sugg');if(!dl||!c)return;var opts=dl.children;var h='';for(var i=0;i<opts.length;i++){var v=opts[i].getAttribute('value')||opts[i].textContent;if(!v)continue;var ve=esc(v);h+='<div class=\\'it\\' data-v=\\''+ve+'\\'>'+ve+'</div>';}c.innerHTML=h;c.style.display=h?'block':'none';}")
        S(b"function buildSuggFromHTML(t){var c=g('ssid_sugg');if(!c)return;var h='';var i=0;while(true){var a=t.indexOf(\\\"value='\\\",i);if(a<0)break;a+=7;var b=t.indexOf(\\\"'\\\",a);if(b<0)break;var v=t.substring(a,b);var ve=esc(v);h+='<div class=\\\\'it\\\\' data-v=\\\\''+ve+'\\\\'>'+ve+'</div>';i=b+1;}c.innerHTML=h;c.style.display=h?'block':'none';}")
        S(b"document.addEventListener('click',function(e){var c=g('ssid_sugg');if(!c)return;var i=g('wifi_ssid');var t=e.target;var cls=(t&&t.classList&&t.classList.contains('it'));var cn=(t&&t.className&&(' '+t.className+' ').indexOf(' it ')>=0);if(cls||cn){if(i){i.value=t.getAttribute('data-v')||t.textContent;i.focus();}c.style.display='none';return;}if(t===i){if(c.innerHTML)c.style.display='block';return;}if(!c.contains(t))c.style.display='none';});")
        S(b"function sc(btn){try{btn.disabled=true;var ot=btn.innerHTML;btn.innerHTML='Scanning...';fetch('/scan?ts='+Date.now(),{cache:'no-store'}).then(function(r){return r.text()}).then(function(t){g('ssid_list').innerHTML=t;btn.innerHTML='Scan';btn.disabled=false;var inp=g('wifi_ssid');if(inp){var v=inp.value;inp.setAttribute('list','');setTimeout(function(){inp.setAttribute('list','ssid_list');inp.value=v+' ';inp.value=v;inp.focus();buildSuggFromHTML(t);},0);}}).catch(function(){btn.innerHTML='Scan';btn.disabled=false;});}catch(e){btn.innerHTML='Scan';btn.disabled=false;}}</script>")
        S(b"</head><body><h1>SensDot Configuration</h1>")
        # form start
        S(b"<form method='POST' autocomplete='off' autocapitalize='none' autocorrect='off' spellcheck='false'>")
        # device identity
        S(b"<section><h3 style='margin:0 0 8px;font-size:16px'>Device Identity</h3>")
        S(b"<label>Device Name<input name='device_name' value='")
        S(self._esc(names.get('device_name', '')).encode())
        S(b"'></label><small>Friendly name for dashboards</small>")
        S(b"<label>MQTT Name<input id='mqtt_name' name='mqtt_name' oninput='vMqttName(this)' value='")
        S(self._esc(names.get('mqtt_name', '')).encode())
        S(b"'></label><div id='mqtt_err' style='display:none;color:#e33;font-size:11px'>Only a-z A-Z 0-9 _ - allowed</div><small>Used as base for topics</small></section>")

        # wifi (with datalist)
        try:
            sta = network.WLAN(network.STA_IF)
            try:
                sta.active(True)
            except:
                pass
            nets = sta.scan()
        except Exception as _e:
            nets = []
        S(b"<section><h3 style='margin:0 0 8px;font-size:16px'>WiFi</h3>")
        S(b"<datalist id='ssid_list'>")
        try:
            c = 0
            if nets:
                for ap in nets:
                    ss = ap[0]
                    if isinstance(ss, bytes):
                        try:
                            ss = ss.decode()
                        except:
                            ss = ''
                    if not ss:
                        continue
                    S(b"<option value='")
                    S(self._esc(ss).encode())
                    S(b"'>")
                    c += 1
                    if c >= 15:
                        break
        except Exception as e:
            es = str(e)
            if ('ETIMEDOUT' in es) or ('ECONNRESET' in es) or ('EPIPE' in es) or ('104' in es) or ('32' in es):
                # common client disconnects during page load; ignore
                pass
            else:
                self._log('warn', 'HTTP error: {}'.format(e))
        S(b"</datalist>")
        S(b"<label>SSID<div class='ssidbox'><div class='ssidrow'><input id='wifi_ssid' name='wifi_ssid' list='ssid_list' autocomplete='off' value='")
        S(self._esc(wifi.get('ssid', '')).encode())
        S(b"' required><button type='button' class='btn-sm' onclick=\"try{this.disabled=true;var ot=this.innerHTML;this.innerHTML='Scanning...';fetch('/scan?ts='+Date.now(),{cache:'no-store'}).then(function(r){return r.text()}).then(function(t){document.getElementById('ssid_list').innerHTML=t;this.innerHTML='Scan';this.disabled=false;var inp=document.getElementById('wifi_ssid');if(inp){var v=inp.value;inp.setAttribute('list','');setTimeout(function(){inp.setAttribute('list','ssid_list');inp.value=v+' ';inp.value=v;inp.focus();if(window.buildSuggFromHTML){buildSuggFromHTML(t);}else if(window.buildSugg){buildSugg();}},0);}}.bind(this)).catch(function(){this.innerHTML='Scan';this.disabled=false;}.bind(this));}catch(e){this.innerHTML='Scan';this.disabled=false;}return false;\">Scan</button></div><div id='ssid_sugg' class='sugg' style='display:none'></div></div></label>")
        S(b"<label>WiFi Password<div class='pwrow'><input id='wifi_password' type='password' name='wifi_password' autocomplete='section-wifi new-password' value='")
        S(self._esc(wifi.get('password', '')).encode())
        S(b"'><button type='button' class='btn-sm' onclick=\"try{var i=document.getElementById('wifi_password');if(i){if(i.type==='password'){i.type='text';this.innerHTML='Hide';}else{i.type='password';this.innerHTML='Show';}}}catch(e){}\">Show</button></div></label><small>Password blank = open network</small></section>")

        # mqtt layout
        S(b"<section><h3 style='margin:0 0 8px;font-size:16px'>MQTT</h3>")
        S(b"<div class='row'><div><label>Broker<input name='mqtt_broker' value='")
        S(self._esc(mqtt.get('broker', '')).encode())
        S(b"' required></label></div><div style='max-width:90px'><label>Port<input name='mqtt_port' type='number' value='")
        S(str(mqtt.get('port', 1883)).encode())
        S(b"' style='width:80px'></label></div></div>")
        S(b"<label>User<input name='mqtt_username' autocomplete='section-mqtt username' value='")
        S(self._esc(mqtt.get('username', '')).encode())
        S(b"'></label>")
        S(b"<label>MQTT Password<div class='pwrow'><input id='mqtt_password' type='password' name='mqtt_password' autocomplete='section-mqtt current-password' value='")
        S(self._esc(mqtt.get('password', '')).encode())
        S(b"'><button type='button' class='btn-sm' onclick=\"try{var i=document.getElementById('mqtt_password');if(i){if(i.type==='password'){i.type='text';this.innerHTML='Hide';}else{i.type='password';this.innerHTML='Show';}}}catch(e){}\">Show</button></div></label><small>Topics will use MQTT Name (e.g., name/data)</small></section>")

        # advanced
        S(b"<button type='button' id='adv_btn' class='adv-toggle' onclick=\"(function(btn){try{var a=document.getElementById('adv');if(!a)return;var has=a.classList&&a.classList.toggle;var hidden=false;if(has){hidden=a.classList.toggle('hidden');}else{var cn=a.className||'';if(cn.indexOf('hidden')>=0){a.className=cn.replace('hidden','');hidden=false;}else{a.className=cn+' hidden';hidden=true;}}btn.innerHTML=hidden?'Show Advanced >':'Hide Advanced v';}catch(e){}})(this)\">Show Advanced ></button>")
        S(b"<div id='adv' class='hidden'>")
        S(b"<section><h3 style='margin:0 0 8px;font-size:16px'>Intervals</h3><div class='row'><div><label>Sleep Interval (s)<input name='sleep_interval' type='number' value='")
        S(str(adv.get('sleep_interval', 60)).encode())
        S(b"'></label></div><div><label>Sensor Interval (s)<input name='sensor_interval' type='number' value='")
        S(str(adv.get('sensor_interval', 30)).encode())
        S(b"'></label></div></div><label style='margin-top:8px'><input type='checkbox' name='mqtt_discovery' ")
        if adv.get('mqtt_discovery', True):
            S(b"checked ")
        S(b"> Enable MQTT Discovery</label></section>")
        S(b"<section><h3 style='margin:0 0 8px;font-size:16px'>Time / NTP</h3><label><input type='checkbox' name='enable_ntp' ")
        if ntp.get('enable_ntp', True):
            S(b"checked ")
        S(b"> Enable NTP Sync</label><label>NTP Server<input name='ntp_server' value='")
        S(self._esc(ntp.get('ntp_server', 'pool.ntp.org')).encode())
        S(b"'></label>")
        S(b"<label>Timezone Preset<select name='tz_preset' onchange=\"try{var p=(this.value||'').split('|');if(p.length>=2){var o=document.getElementById('tz_off');if(o){o.value=p[0];}var d=document.getElementById('dst_region');if(d){for(var i=0;i<d.options.length;i++){if(d.options[i].value===p[1]){d.selectedIndex=i;break;}}}}}catch(e){}\">")
        S(b"<option value=''>-- Select city (optional) --</option>")
        # UTC-
        S(b"<option value='-10|NONE'>Honolulu (UTC-10, No DST)</option>")
        S(b"<option value='-9|US'>Anchorage (UTC-9, US)</option>")
        S(b"<option value='-8|US'>Los Angeles/San Francisco (UTC-8, US)</option>")
        S(b"<option value='-7|US'>Denver/Phoenix (UTC-7, US)</option>")
        S(b"<option value='-6|US'>Chicago/Mexico City (UTC-6, US)</option>")
        S(b"<option value='-5|US'>New York/Toronto (UTC-5, US)</option>")
        S(b"<option value='-4|SA'>Santiago (UTC-4, SA)</option>")
        S("<option value='-3|SA'>Buenos Aires/São Paulo (UTC-3, SA)</option>".encode())
        S("<option value='-5|NONE'>Lima/Bogotá (UTC-5, No DST)</option>".encode())
        # UTC 0
        S(b"<option value='0|NONE'>UTC (UTC+0)</option>")
        S(b"<option value='0|EU'>London/Dublin (UTC+0, EU)</option>")
        S(b"<option value='0|AFRICA'>Lisbon/Casablanca (UTC+0, AFRICA)</option>")
        # UTC+
        S(b"<option value='1|NONE'>Lagos/Kinshasa (UTC+1, No DST)</option>")
        S(b"<option value='1|EU'>Paris/Berlin/Rome (UTC+1, EU)</option>")
        S(b"<option value='2|NONE'>Cairo/Johannesburg (UTC+2, No DST)</option>")
        S(b"<option value='2|EU'>Athens/Helsinki/Istanbul (UTC+2, EU)</option>")
        S(b"<option value='3|NONE'>Moscow/Nairobi (UTC+3, No DST)</option>")
        S(b"<option value='3.5|ME'>Tehran (UTC+3.5, ME)</option>")
        S(b"<option value='4|NONE'>Dubai/Abu Dhabi (UTC+4, No DST)</option>")
        S(b"<option value='5.5|NONE'>India (IST) (UTC+5.5, No DST)</option>")
        S(b"<option value='7|NONE'>Bangkok/Jakarta (UTC+7, No DST)</option>")
        S(b"<option value='8|NONE'>Beijing/Hong Kong/Singapore (UTC+8, No DST)</option>")
        S(b"<option value='8|NONE'>Perth (UTC+8, No DST)</option>")
        S(b"<option value='9|NONE'>Tokyo/Seoul (UTC+9, No DST)</option>")
        S(b"<option value='9.5|AU'>Adelaide (UTC+9.5, AU)</option>")
        S(b"<option value='10|AU'>Sydney/Melbourne (UTC+10, AU)</option>")
        S(b"<option value='12|AU'>Auckland (UTC+12, AU)</option>")
        S(b"</select></label>")
        S(b"<div class='row'><div><label>Timezone Offset (hrs)<input id='tz_off' name='timezone_offset' type='number' step='0.5' value='")
        S(str(ntp.get('timezone_offset', 0)).encode())
        S(b"'></label></div>")
        S(b"<div><label>DST Region<select id='dst_region' name='dst_region'>")
        for code, label in [('NONE', 'None'), ('EU', 'Europe'), ('US', 'US/Canada'), ('AU', 'Australia'), ('SA','South America'), ('ME','Middle East'), ('AFRICA','Africa')]:
            sel = b" selected" if ntp.get('dst_region', 'NONE') == code else b""
            S(b"<option value='" + code.encode() + b"'" + sel + b">" + label.encode() + b"</option>")
        S(b"</select></label></div></div><label>Sync Interval (s)<input name='ntp_sync_interval' type='number' value='")
        S(str(ntp.get('ntp_sync_interval', 3600)).encode())
        S(b"'></label></section>")
        S(b"</div>")  # end adv

        # submit
        S(b"<button id='save' class='submit' type='submit'>Save & Reboot</button>")
        S(b"</form><p style='text-align:center;font-size:11px;color:#666;margin-bottom:24px'>SensDot setup portal</p>")
        S(b"</body></html>")
        try:
            conn.close()
        except:
            pass
        gc.collect()
        self._log('info', 'Config page served')

    # ---------- Responses ----------
    def _send_success_response(self, conn):
        html = ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Saved</title><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<style>body{font-family:Arial;background:#eef;text-align:center;padding:40px}.card{background:#fff;padding:24px;border-radius:10px;max-width:420px;margin:0 auto;box-shadow:0 2px 6px rgba(0,0,0,.15)}.spinner{width:46px;height:46px;border:5px solid #ddd;border-top:5px solid #4a67d6;border-radius:50%;animation:spin 1s linear infinite;margin:18px auto}@keyframes spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}</style></head><body><div class='card'><h2>Configuration Saved</h2><p>Device rebooting...</p><div class='spinner'></div><p>You can now disconnect from the AP.</p></div></body></html>")
        resp = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}".format(len(html), html)
        try:
            conn.send(resp.encode())
        except:
            pass
        try:
            conn.close()
        except:
            pass

    def _send_error_response(self, conn, msg):
        html = ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Error</title>"
                "<style>body{font-family:Arial;background:#fee;text-align:center;padding:40px}.card{background:#fff;padding:24px;border-radius:10px;max-width:420px;margin:0 auto;border:1px solid #e88}</style>"
                "</head><body><div class='card'><h2>Error</h2><p>" + self._esc(msg) + "</p><p><a href='/'>Back</a></p></div></body></html>")
        resp = "HTTP/1.1 400 Bad Request\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}".format(len(html), html)
        try:
            conn.send(resp.encode())
        except:
            pass
        try:
            conn.close()
        except:
            pass

    def _send_404(self, conn):
        resp = b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nConnection: close\r\nContent-Length: 13\r\n\r\n404 Not Found"
        try:
            conn.send(resp)
        except:
            pass
        try:
            conn.close()
        except:
            pass

    def _esc(self, s):
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;') if isinstance(s, str) else ''

    # ---------- Scan Endpoint ----------
    def _send_scan_list(self, conn):
        try:
            try:
                # Begin scan diagnostics
                try:
                    self._log('info', '/scan: begin')
                except:
                    pass
                sta = network.WLAN(network.STA_IF)
                try:
                    sta.active(True)
                except:
                    pass
                nets = sta.scan()
            except Exception as _e:
                nets = []
                try:
                    self._log('warn', '/scan: scan failed: {}'.format(_e))
                except:
                    pass

            options = []
            c = 0
            if nets:
                for ap in nets:
                    ss = ap[0]
                    if isinstance(ss, bytes):
                        try:
                            ss = ss.decode()
                        except:
                            ss = ''
                    if not ss:
                        continue
                    options.append("<option value='" + self._esc(ss) + "'>")
                    c += 1
                    if c >= 20:
                        break
            # Log count
            try:
                self._log('info', '/scan: found {} nets, returning {}'.format(len(nets) if nets else 0, len(options)))
            except:
                pass
            body = ''.join(options)
            resp = "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}".format(len(body), body)
            try:
                conn.send(resp.encode())
            except:
                pass
        finally:
            try:
                conn.close()
            except:
                pass


# ---------- Standalone Helper ----------
def start_simple_ap():
    cfg = ConfigManager()
    WiFiConfigServer(cfg).start_config_server()


if __name__ == '__main__':  # pragma: no cover
    start_simple_ap()
