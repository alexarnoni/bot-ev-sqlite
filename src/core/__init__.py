"""
Core package - foundational modules (config, logging, database)
"""
from src.core.config import FEED_ID, BASE_PATH, feed_path, get_telegram_token, get_database_path
from src.core.database import get_db, Database, generate_alert_hash
from src.core.logging_config import get_logger, get_general_logger, get_scan_logger
