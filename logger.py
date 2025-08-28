# logger.py
# Logging system with file rotation for SensDot device
# Provides centralized logging with configurable levels and file rotation

import time
import sys

class Logger:
    """
    Centralized logging system with file rotation for MicroPython
    Features:
    - Multiple log levels (DEBUG, INFO, WARN, ERROR, CRITICAL)
    - File rotation based on size
    - Console and file output
    - Memory-efficient implementation for ESP32
    """
    
    # Log levels
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40
    CRITICAL = 50
    
    LEVEL_NAMES = {
        DEBUG: "DEBUG",
        INFO: "INFO", 
        WARN: "WARN",
        ERROR: "ERROR",
        CRITICAL: "CRITICAL"
    }
    
    def __init__(self, name="SensDot", log_file="sensdot.log", 
                 max_file_size=10240, max_files=3, level=INFO, 
                 console_output=True):
        """
        Initialize logger
        
        Args:
            name: Logger name
            log_file: Primary log file name (will be placed in logs/ directory)
            max_file_size: Maximum size per log file in bytes (default 10KB)
            max_files: Maximum number of rotated files to keep
            level: Minimum log level to record
            console_output: Whether to also output to console
        """
        self.name = name
        # Add logs/ directory prefix if not already present
        if not log_file.startswith('logs/'):
            self.log_file = f"logs/{log_file}"
        else:
            self.log_file = log_file
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.level = level
        self.console_output = console_output
        
        # Ensure logs directory exists
        self._ensure_logs_directory()
        
    def _ensure_logs_directory(self):
        """Ensure logs directory exists"""
        try:
            import os
            # Try to create logs directory
            try:
                os.mkdir('logs')
            except OSError:
                # Directory might already exist, check if it's accessible
                try:
                    os.listdir('logs')
                except OSError:
                    # Directory doesn't exist and can't be created, fall back to root
                    if self.console_output:
                        print("Warning: Could not create logs directory, using root")
                    self.log_file = self.log_file.replace('logs/', '')
        except ImportError:
            # os module not available, fall back to root directory
            if self.console_output:
                print("Warning: os module not available, using root directory")
            self.log_file = self.log_file.replace('logs/', '')
        
    def _get_timestamp(self):
        """Get formatted timestamp for log entries"""
        try:
            # Get current time (time since boot in seconds)
            t = time.time()
            
            # Convert to readable format (basic implementation)
            # Since MicroPython doesn't have datetime, we use simple formatting
            days = int(t // 86400)
            hours = int((t % 86400) // 3600)
            minutes = int((t % 3600) // 60)
            seconds = int(t % 60)
            
            return f"{days:03d}d{hours:02d}:{minutes:02d}:{seconds:02d}"
        except:
            # Fallback if time functions fail
            return f"{time.ticks_ms():010d}"
    
    def _rotate_files(self):
        """Rotate log files when size limit is reached"""
        try:
            # Check if current log file exists and its size
            try:
                with open(self.log_file, 'r') as f:
                    f.seek(0, 2)  # Seek to end
                    size = f.tell()
                    
                if size < self.max_file_size:
                    return  # No rotation needed
                    
            except OSError:
                return  # File doesn't exist, no rotation needed
            
            # Perform rotation
            # Delete oldest file first
            if self.max_files > 1:
                oldest_file = f"{self.log_file}.{self.max_files - 1}"
                try:
                    import os
                    os.remove(oldest_file)
                except OSError:
                    pass  # File doesn't exist
                
                # Shift existing files
                for i in range(self.max_files - 2, 0, -1):
                    old_name = f"{self.log_file}.{i}"
                    new_name = f"{self.log_file}.{i + 1}"
                    try:
                        os.rename(old_name, new_name)
                    except OSError:
                        pass  # File doesn't exist
                
                # Move current log to .1
                try:
                    os.rename(self.log_file, f"{self.log_file}.1")
                except OSError:
                    pass
                    
        except Exception as e:
            # If rotation fails, continue without rotation
            # This prevents logging system from crashing the device
            if self.console_output:
                print(f"Log rotation failed: {e}")
    
    def _write_log(self, level, message):
        """Write log entry to file and/or console"""
        if level < self.level:
            return  # Below minimum log level
        
        timestamp = self._get_timestamp()
        level_name = self.LEVEL_NAMES.get(level, "UNKNOWN")
        log_entry = f"[{timestamp}] {level_name:8s} {self.name}: {message}"
        
        # Output to console if enabled
        if self.console_output:
            print(log_entry)  # print() automatically adds newline
        
        # Write to file with explicit newline
        try:
            # Check if rotation is needed before writing
            self._rotate_files()
            
            with open(self.log_file, 'a') as f:
                f.write(log_entry + '\n')  # Explicit newline addition
                f.flush()  # Ensure data is written to flash
                
        except Exception as e:
            # If file logging fails, at least try console output
            if self.console_output:
                print(f"Log file write failed: {e}")
    
    def debug(self, message):
        """Log debug message"""
        self._write_log(self.DEBUG, str(message))
    
    def info(self, message):
        """Log info message"""
        self._write_log(self.INFO, str(message))
    
    def warn(self, message):
        """Log warning message"""
        self._write_log(self.WARN, str(message))
    
    def warning(self, message):
        """Alias for warn()"""
        self.warn(message)
    
    def error(self, message):
        """Log error message"""
        self._write_log(self.ERROR, str(message))
    
    def critical(self, message):
        """Log critical message"""
        self._write_log(self.CRITICAL, str(message))
    
    def exception(self, message="Exception occurred"):
        """Log exception with traceback (MicroPython compatible)"""
        try:
            # Simply log the message as an error
            # MicroPython doesn't have sys.exc_info() like CPython
            self._write_log(self.ERROR, message)
            
            # Try to print exception traceback if available
            try:
                import sys
                # In MicroPython, sys.print_exception() without arguments 
                # prints the current exception if called from except block
                sys.print_exception()
            except:
                # If that fails, just note that exception details aren't available
                if self.console_output:
                    print("(Exception traceback not available)")
                
        except Exception as e:
            self._write_log(self.ERROR, f"Exception logging failed: {e}")
    
    def set_level(self, level):
        """Set minimum log level"""
        self.level = level
    
    def get_log_stats(self):
        """Get logging statistics"""
        stats = {
            "log_file": self.log_file,
            "level": self.LEVEL_NAMES.get(self.level, "UNKNOWN"),
            "console_output": self.console_output,
            "max_file_size": self.max_file_size,
            "max_files": self.max_files
        }
        
        # Get current log file size and verify file ending
        try:
            with open(self.log_file, 'rb') as f:
                f.seek(0, 2)  # Seek to end
                size = f.tell()
                stats["current_size"] = size
                
                # Check last few bytes to verify proper line ending
                if size > 0:
                    f.seek(max(0, size - 10))
                    last_bytes = f.read()
                    stats["ends_with_newline"] = last_bytes.endswith(b'\n')
                else:
                    stats["ends_with_newline"] = True
                    
        except OSError:
            stats["current_size"] = 0
            stats["ends_with_newline"] = True
        
        return stats
    
    def clear_logs(self):
        """Clear all log files"""
        try:
            import os
            
            # Remove main log file
            try:
                os.remove(self.log_file)
            except OSError:
                pass
            
            # Remove rotated files
            for i in range(1, self.max_files):
                try:
                    os.remove(f"{self.log_file}.{i}")
                except OSError:
                    pass
                    
            self.info("Log files cleared")
            
        except Exception as e:
            if self.console_output:
                print(f"Failed to clear logs: {e}")


# Global logger instance
_global_logger = None

def get_logger(name="SensDot", **kwargs):
    """Get a logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger(name, **kwargs)
    return _global_logger

def setup_logging(config_manager=None, console_output=True):
    """
    Setup logging system based on configuration
    
    Args:
        config_manager: ConfigManager instance for getting log settings
        console_output: Whether to enable console output
    
    Returns:
        Logger instance
    """
    global _global_logger
    
    # Default settings
    log_settings = {
        "log_file": "logs/sensdot.log",  # Use logs directory
        "max_file_size": 10240,  # 10KB
        "max_files": 3,
        "level": Logger.INFO,
        "console_output": console_output
    }
    
    # Get settings from config if available
    if config_manager:
        try:
            advanced_config = config_manager.get_advanced_config()
            
            # Use debug mode from config to set log level
            if advanced_config.get('debug_mode', False):
                log_settings["level"] = Logger.DEBUG
            
            # Get logging config if available
            try:
                log_config = config_manager.get_logging_config()
                log_settings["max_file_size"] = log_config.get('log_file_size', 10240)
                log_settings["max_files"] = log_config.get('log_files_count', 3)
                
                # Convert log level string to constant
                level_str = log_config.get('log_level', 'INFO').upper()
                if hasattr(Logger, level_str):
                    log_settings["level"] = getattr(Logger, level_str)
                    
            except:
                pass  # Use defaults if logging config not available
            
            # Get device name for logger name
            device_names = config_manager.get_device_names()
            logger_name = device_names.get('device_name', 'SensDot')
            
        except Exception as e:
            logger_name = "SensDot"
            if console_output:
                print(f"Could not get config for logging: {e}")
    else:
        logger_name = "SensDot"
    
    # Create logger instance
    _global_logger = Logger(name=logger_name, **log_settings)
    
    return _global_logger

# Convenience functions for global logger
def debug(message):
    """Log debug message using global logger"""
    if _global_logger:
        _global_logger.debug(message)

def info(message):
    """Log info message using global logger"""
    if _global_logger:
        _global_logger.info(message)

def warn(message):
    """Log warning message using global logger"""
    if _global_logger:
        _global_logger.warn(message)

def error(message):
    """Log error message using global logger"""
    if _global_logger:
        _global_logger.error(message)

def critical(message):
    """Log critical message using global logger"""
    if _global_logger:
        _global_logger.critical(message)

def exception(message="Exception occurred"):
    """Log exception using global logger"""
    if _global_logger:
        _global_logger.exception(message)
