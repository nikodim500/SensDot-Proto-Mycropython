import time
import network
try:
    from config_manager import ConfigManager
except Exception as e:
    print('Config import error:', e)
    ConfigManager = None

def status_name(code):
    names = {
        0: 'IDLE',
        1: 'CONNECTING',
        2: 'WRONG_PASSWORD',
        3: 'NO_AP_FOUND',
        4: 'FAIL',
        5: 'GOT_IP',
    }
    return names.get(code, str(code))

def main():
    sta = network.WLAN(network.STA_IF)
    try:
        sta.active(False)
        time.sleep(0.1)
    except:
        pass
    sta.active(True)

    ssid = ''
    pwd = ''
    if ConfigManager:
        cfg = ConfigManager()
        wifi = cfg.get_wifi_config()
        ssid = wifi.get('ssid') or ''
        pwd = wifi.get('password') or ''

    print('--- WiFi Diagnostics ---')
    print('Configured SSID:', ssid)
    print('Password length:', len(pwd))

    # Scan
    try:
        nets = sta.scan()
        print('Scan results:', len(nets) if nets else 0)
        found = False
        if nets:
            for ap in nets[:15]:
                essid = ap[0].decode() if isinstance(ap[0], bytes) else ap[0]
                rssi = ap[3]
                auth = ap[4]
                print('  -', essid, 'RSSI', rssi, 'auth', auth)
                if essid == ssid:
                    found = True
        if not found and ssid:
            print('WARN: Configured SSID not found in scan (check 2.4GHz / range)')
    except Exception as e:
        print('Scan error:', e)

    if not ssid:
        print('No SSID configured; aborting connect test')
        return

    # Connect
    try:
        print('Connecting to', ssid)
        sta.connect(ssid, pwd)
    except Exception as e:
        print('connect() error:', e)
        return

    for i in range(35):
        try:
            st = None
            try:
                st = sta.status()
            except:
                pass
            ic = sta.isconnected()
            print('t+%02ds  status:' % i, status_name(st) if isinstance(st,int) else st, ' isconnected:', ic)
            if ic:
                print('ifconfig:', sta.ifconfig())
                break
            time.sleep(1)
        except Exception as e:
            print('wait error:', e)
            break

    if not sta.isconnected():
        print('Final: connection not established')

if __name__ == '__main__':
    main()
