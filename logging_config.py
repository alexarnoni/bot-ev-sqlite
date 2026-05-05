"""
Centralized logging configuration with rotation and secret masking
"""
import os
import re
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional
from config import FEED_ID, BASE_PATH

class SecretMaskingFormatter(logging.Formatter):
    """Custom formatter that masks sensitive information in log messages"""
    
    # Patterns to mask (case-insensitive)
    SECRET_PATTERNS = [
        r'(api[_-]?key\s*[=:]\s*)([a-zA-Z0-9_-]+)',
        r'(key\s*[=:]\s*)([a-zA-Z0-9_-]{8,})',
        r'(token\s*[=:]\s*)([a-zA-Z0-9_-]+)',
        r'(BOT_TOKEN_[A-Z0-9_]+\s*[=:]\s*)([a-zA-Z0-9_-]+)',
        r'(password\s*[=:]\s*)([^\s]+)',
        r'(secret\s*[=:]\s*)([^\s]+)',
        r'([a-zA-Z0-9_-]{20,})',  # Generic long strings that might be keys
    ]
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt, datefmt)
        self._compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SECRET_PATTERNS]
    
    def format(self, record):
        # Get the formatted message
        msg = super().format(record)
        
        # Apply masking
        for pattern in self._compiled_patterns:
            msg = pattern.sub(r'\1***MASKED***', msg)
        
        return msg

def setup_logging(
    name: str,
    level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Sets up a logger with rotation and secret masking
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maximum size per log file before rotation
        backup_count: Number of backup files to keep
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Custom formatter with secret masking
    formatter = SecretMaskingFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation
    if log_to_file:
        # Create logs directory structure: logs/{feed_id}/
        log_dir = os.path.join(BASE_PATH, "logs", FEED_ID)
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"{name}.log")
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Get a logger instance with default configuration"""
    return setup_logging(name, level)

# Pre-configured loggers for common use cases
def get_general_logger() -> logging.Logger:
    """Get logger for general bot operations"""
    return get_logger("bot_general")

def get_scan_logger() -> logging.Logger:
    """Get logger for scan operations"""
    return get_logger("bot_scan")

def get_alerts_logger() -> logging.Logger:
    """Get logger for alert operations"""
    return get_logger("bot_alerts")

def get_api_logger() -> logging.Logger:
    """Get logger for API operations"""
    return get_logger("bot_api")

def get_database_logger() -> logging.Logger:
    """Get logger for database operations"""
    return get_logger("bot_database")

# Test function to verify masking works
def test_secret_masking():
    """Test function to verify secret masking is working"""
    logger = get_logger("test_masking")
    
    # These should be masked in the logs
    logger.info("API key: abc123def456")
    logger.info("BOT_TOKEN_FEED1=xyz789")
    logger.info("key: verylongsecretkey123456789")
    logger.info("password=secretpass")
    
    # This should not be masked (too short)
    logger.info("key: abc")
    
    print("Secret masking test completed. Check logs to verify masking.")
