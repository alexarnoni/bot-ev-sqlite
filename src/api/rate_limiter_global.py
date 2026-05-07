"""
Rate limiter GLOBAL centralizado (independente de feed/processo)
Usa SQLite em data/global/rate_limit.db
"""
import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


class GlobalRateLimiter:
    def __init__(self, db_path: Optional[str] = None, max_requests_per_hour: int = 3000):
        base_dir = os.path.join(os.getcwd(), 'data', 'global')
        _ensure_dir(base_dir)
        self.db_path = db_path or os.path.join(base_dir, 'rate_limit.db')
        self.max_requests = max_requests_per_hour
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        try:
            conn.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass
        try:
            conn.execute("PRAGMA busy_timeout=5000")
        except Exception:
            pass
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_timestamp TIMESTAMP NOT NULL,
                    endpoint TEXT,
                    api_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_requests_ts ON api_requests(request_timestamp)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    scan_timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_scans_time ON user_scans(scan_timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_scans_chat ON user_scans(chat_id)")

    # ---- API requests ----
    def get_request_count_last_hour(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM api_requests
                WHERE request_timestamp >= datetime('now', '-1 hour')
                """
            ).fetchone()
            return int(row['c']) if row else 0

    def can_make_request(self) -> bool:
        return self.get_request_count_last_hour() < self.max_requests

    def log_request(self, endpoint: str = '/value-bets', api_key: Optional[str] = None) -> None:
        with self._connect() as conn:
            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                "INSERT INTO api_requests (request_timestamp, endpoint, api_key) VALUES (?, ?, ?)",
                (now, endpoint, api_key or ''),
            )

    # ---- User scans ----
    def log_user_scan(self, chat_id: str) -> None:
        with self._connect() as conn:
            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                "INSERT INTO user_scans (chat_id, scan_timestamp) VALUES (?, ?)",
                (str(chat_id), now),
            )

    def get_user_scan_count(self, chat_id: str, window: str = "-1 minute") -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM user_scans
                WHERE chat_id = ? AND scan_timestamp >= datetime('now', ?)
                """,
                (str(chat_id), window),
            ).fetchone()
            return int(row['c']) if row else 0

    def can_user_scan(self, chat_id: str, per_minute: int = 2, per_hour: int = 30) -> bool:
        return self.get_user_scan_count(chat_id, "-1 minute") < per_minute and \
               self.get_user_scan_count(chat_id, "-1 hour") < per_hour

    # ---- Stats ----
    def get_stats(self) -> Dict[str, int]:
        return {
            'requests_last_hour': self.get_request_count_last_hour(),
        }


_global_rl: Optional[GlobalRateLimiter] = None


def get_global_rate_limiter() -> GlobalRateLimiter:
    global _global_rl
    if _global_rl is None:
        # RATE_LIMIT_REQUESTS_PER_HOUR vem do config; se indisponível, fallback 3000
        try:
            from src.core.config import RATE_LIMIT_REQUESTS_PER_HOUR
            _global_rl = GlobalRateLimiter(max_requests_per_hour=RATE_LIMIT_REQUESTS_PER_HOUR)
        except Exception:
            _global_rl = GlobalRateLimiter()
    return _global_rl
