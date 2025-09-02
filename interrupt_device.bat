@echo off
echo Interrupting ESP32 device...
mpremote connect port:COM3 exec "print('=== DEVICE INTERRUPTED ==='); import sys; sys.exit()"
echo Device process stopped. Ready for new commands.
