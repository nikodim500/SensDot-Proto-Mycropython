# ntp_client.py
# NTP client for SensDot device to synchronize time
# Provides accurate timestamps for logging and device operations

import socket
import struct
import time
import network

class NTPClient:
    """
    Network Time Protocol client for MicroPython
    Synchronizes device time with NTP servers for accurate timestamps
    """
    
    # NTP server list (prioritized by reliability and global availability)
    NTP_SERVERS = [
        "pool.ntp.org",
        "time.nist.gov", 
        "time.google.com",
        "time.cloudflare.com",
        "0.pool.ntp.org",
        "1.pool.ntp.org"
    ]
    
    # NTP constants
    NTP_DELTA = 2208988800  # Offset between NTP epoch (1900) and Unix epoch (1970)
    NTP_PORT = 123
    NTP_TIMEOUT = 5  # seconds
    
    def __init__(self, logger=None, timezone_offset=0, dst_region="NONE"):
        """
        Initialize NTP client
        
        Args:
            logger: Logger instance for debug output
            timezone_offset: Base timezone offset in hours from UTC (e.g., 0 for GMT, 1 for CET)
            dst_region: DST region ("EU", "US", "AU", "SA", "ME", "AFRICA", "NONE") for automatic DST handling
        """
        self.logger = logger
        self.base_timezone_offset = timezone_offset
        self.dst_region = dst_region
        self.timezone_offset = timezone_offset  # Will be updated with DST
        self.last_sync_time = 0
        self.sync_interval = 3600  # Sync every hour by default
        
    def _update_timezone_with_dst(self):
        """Update timezone offset to include DST if applicable"""
        if self.dst_region == "NONE":
            self.timezone_offset = self.base_timezone_offset
            return
            
        try:
            import time
            current_time = time.localtime()
            month = current_time[1]
            day = current_time[2]
            
            # Simple DST calculation
            is_dst = self._is_dst_active(month, day)
            dst_offset = 1 if is_dst else 0
            
            self.timezone_offset = self.base_timezone_offset + dst_offset
            
        except Exception as e:
            self._log("warn", f"DST calculation failed: {e}")
            self.timezone_offset = self.base_timezone_offset

    def _is_dst_active(self, month, day):
        """DST check for multiple global regions"""
        if self.dst_region == "EU":
            # EU: Last Sunday in March to last Sunday in October (approximate)
            return month > 3 and month < 10 or \
                   (month == 3 and day >= 25) or \
                   (month == 10 and day <= 25)
        elif self.dst_region == "US":
            # US: Second Sunday in March to first Sunday in November (approximate)
            return month > 3 and month < 11 or \
                   (month == 3 and day >= 8) or \
                   (month == 11 and day <= 7)
        elif self.dst_region == "AU":
            # Australia: First Sunday in October to first Sunday in April (approximate)
            return month >= 10 or month <= 4
        elif self.dst_region == "SA":
            # South America: Third Sunday in October to third Sunday in February (approximate)
            return month >= 10 or month <= 2 or \
                   (month == 3 and day <= 15)
        elif self.dst_region == "ME":
            # Middle East (Iran): Third Friday in March to third Friday in October (approximate)
            return month > 3 and month < 10 or \
                   (month == 3 and day >= 20) or \
                   (month == 10 and day <= 20)
        elif self.dst_region == "AFRICA":
            # Africa (Morocco): Last Sunday in March to last Sunday in October (approximate)
            return month > 3 and month < 10 or \
                   (month == 3 and day >= 25) or \
                   (month == 10 and day <= 25)
        
        return False

    def _log(self, level, message):
        """Internal logging helper"""
        if self.logger:
            if level == "debug":
                self.logger.debug(message)
            elif level == "info":
                self.logger.info(message)
            elif level == "warn":
                self.logger.warn(message)
            elif level == "error":
                self.logger.error(message)

    def _create_ntp_packet(self):
        """Create NTP request packet"""
        # NTP packet format: 48 bytes
        packet = bytearray(48)
        
        # Set LI (leap indicator), VN (version), Mode (client)
        packet[0] = 0x1B  # 00 011 011 (no warning, version 3, client mode)
        
        return packet

    def _parse_ntp_response(self, response):
        """Parse NTP response packet and return timestamp"""
        if len(response) < 48:
            raise ValueError("Invalid NTP response length")
        
        # Extract transmit timestamp (bytes 40-47)
        # NTP timestamp is 64-bit: 32-bit seconds + 32-bit fraction
        timestamp_bytes = response[40:48]
        timestamp_int = struct.unpack("!Q", timestamp_bytes)[0]
        
        # Convert from NTP 64-bit format to seconds
        # Upper 32 bits are seconds since 1900
        seconds = timestamp_int >> 32
        
        # Convert from NTP epoch (1900) to Unix epoch (1970)
        unix_timestamp = seconds - self.NTP_DELTA
        
        return unix_timestamp

    def sync_time(self, server=None, retries=3):
        """
        Synchronize time with NTP server
        
        Args:
            server: NTP server hostname (uses default if None)
            retries: Number of retry attempts
            
        Returns:
            bool: True if sync successful, False otherwise
        """
        # Update DST offset before syncing
        self._update_timezone_with_dst()
        
        servers_to_try = [server] if server else self.NTP_SERVERS
        
        for current_server in servers_to_try:
            if not current_server:
                continue
                
            for attempt in range(retries):
                try:
                    self._log("debug", f"NTP sync attempt {attempt + 1}/{retries} with {current_server}")
                    
                    # Resolve server address
                    try:
                        addr_info = socket.getaddrinfo(current_server, self.NTP_PORT)[0]
                        server_addr = addr_info[-1]
                    except Exception as e:
                        self._log("warn", f"Failed to resolve {current_server}: {e}")
                        continue
                    
                    # Create UDP socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.settimeout(self.NTP_TIMEOUT)
                    
                    try:
                        # Send NTP request
                        packet = self._create_ntp_packet()
                        sock.sendto(packet, server_addr)
                        
                        # Receive response
                        response, addr = sock.recvfrom(48)
                        
                        # Parse timestamp
                        unix_timestamp = self._parse_ntp_response(response)
                        
                        # Apply timezone offset (convert to seconds and ensure integer)
                        timezone_seconds = int(self.timezone_offset * 3600)
                        local_timestamp = unix_timestamp + timezone_seconds
                        
                        # Convert to ESP32 epoch (2000-01-01)
                        ESP32_EPOCH_OFFSET = 946684800  # Seconds between 1970 and 2000
                        esp32_timestamp = local_timestamp - ESP32_EPOCH_OFFSET
                        
                        # Set system time
                        time_tuple = time.gmtime(esp32_timestamp)
                        import machine
                        machine.RTC().datetime((
                            time_tuple[0],      # year
                            time_tuple[1],      # month
                            time_tuple[2],      # day
                            time_tuple[6],      # weekday
                            time_tuple[3],      # hour
                            time_tuple[4],      # minute
                            time_tuple[5],      # second
                            0                   # subsecond
                        ))
                        
                        self.last_sync_time = time.time()
                        dst_info = f" (DST active)" if self.dst_region != "NONE" and self._is_dst_active(time_tuple[1], time_tuple[2]) else ""
                        self._log("info", f"Time synchronized with {current_server}, timezone UTC{'+' if self.timezone_offset >= 0 else ''}{self.timezone_offset}{dst_info}")
                        return True
                        
                    finally:
                        sock.close()
                        
                except Exception as e:
                    self._log("warn", f"NTP sync failed (attempt {attempt + 1}): {e}")
                    if attempt == retries - 1:
                        self._log("error", f"All NTP sync attempts failed for {current_server}")
        
        self._log("error", "NTP synchronization failed with all servers")
        return False

    def is_time_synced(self):
        """Check if time was recently synchronized"""
        if self.last_sync_time == 0:
            return False
        
        current_time = time.time()
        time_since_sync = current_time - self.last_sync_time
        return time_since_sync < self.sync_interval

    def get_formatted_time(self, timestamp=None):
        """
        Get formatted time string
        
        Args:
            timestamp: Unix timestamp (uses current time if None)
            
        Returns:
            str: Formatted time string (YYYY-MM-DD HH:MM:SS)
        """
        try:
            if timestamp is None:
                # Use current local time
                time_tuple = time.localtime()
            else:
                # Check if timestamp needs ESP32 epoch conversion
                if timestamp > 1000000000:
                    # Convert to ESP32 epoch for proper display
                    ESP32_EPOCH_OFFSET = 946684800
                    esp32_timestamp = timestamp - ESP32_EPOCH_OFFSET
                    time_tuple = time.localtime(esp32_timestamp)
                else:
                    # Already in ESP32 format
                    time_tuple = time.localtime(timestamp)
            
            # Format as YYYY-MM-DD HH:MM:SS
            return f"{time_tuple[0]:04d}-{time_tuple[1]:02d}-{time_tuple[2]:02d} {time_tuple[3]:02d}:{time_tuple[4]:02d}:{time_tuple[5]:02d}"
        except Exception as e:
            # Fallback if formatting fails
            return f"time_error[{e}]"
    
    def auto_sync_if_needed(self):
        """Automatically sync time if needed (called periodically)"""
        if not self.is_time_synced():
            self._log("info", "Time sync needed, attempting synchronization...")
            return self.sync_time()
        return True
    
    def set_timezone_offset(self, hours):
        """Set timezone offset in hours from UTC"""
        self.base_timezone_offset = hours
        self.timezone_offset = hours
        self._log("info", f"Timezone offset set to UTC{'+' if hours >= 0 else ''}{hours}")
    
    def set_sync_interval(self, seconds):
        """Set automatic sync interval in seconds"""
        # Ensure seconds is an integer
        try:
            seconds = int(seconds)
        except (ValueError, TypeError):
            self._log("warn", f"Invalid sync interval '{seconds}', using default 3600s")
            seconds = 3600
        
        self.sync_interval = max(600, seconds)  # Minimum 10 minutes
        self._log("info", f"Sync interval set to {self.sync_interval} seconds")


# Global NTP client instance
_global_ntp_client = None

def get_ntp_client(logger=None, timezone_offset=0, dst_region="NONE"):
    """Get global NTP client instance"""
    global _global_ntp_client
    if _global_ntp_client is None:
        _global_ntp_client = NTPClient(logger, timezone_offset, dst_region)
    return _global_ntp_client

def sync_time_now(logger=None, server=None):
    """Convenience function to sync time immediately"""
    ntp_client = get_ntp_client(logger)
    return ntp_client.sync_time(server)

def get_current_time_formatted():
    """Get current time in formatted string"""
    ntp_client = get_ntp_client()
    return ntp_client.get_formatted_time()
