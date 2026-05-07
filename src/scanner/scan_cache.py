"""
Snapshot cache para reaproveitar o último resultado do scan global

Armazena em SQLite global (data/global/global_cache.db) um JSON com:
{
  "bookmakers": [str, ...],
  "timestamp": "ISO8601",
  "eventos": [ {evento...}, ... ]
}

Chave de cache usada: "global_snapshot"
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import json
import os
import sqlite3
from contextlib import contextmanager

class GlobalSnapshotCache:
    CACHE_KEY = "global_snapshot"

    def __init__(self):
        self.db_path = os.path.join(os.getcwd(), 'data', 'global', 'global_cache.db')
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Inicializa o banco global de cache"""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    response_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    @contextmanager
    def get_connection(self):
        """Context manager para conexões com o banco global"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def set_snapshot(self, eventos: List[Dict[str, Any]], bookmakers: List[str], timestamp: datetime) -> None:
        """Salva o snapshot atual na tabela api_cache global.

        - eventos: lista de eventos retornados do scan global
        - bookmakers: lista de casas usadas no lote
        - timestamp: momento do scan (UTC)
        """
        payload = {
            "bookmakers": list(dict.fromkeys(bookmakers or [])),  # de-dup preservando ordem
            "timestamp": (timestamp.astimezone(timezone.utc).isoformat() if isinstance(timestamp, datetime) else str(timestamp)),
            "eventos": eventos or [],
        }

        doc = json.dumps(payload, ensure_ascii=False)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO api_cache (cache_key, response_json, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json = excluded.response_json,
                    created_at = CURRENT_TIMESTAMP
                """,
                (self.CACHE_KEY, doc),
            )

    def get_snapshot(self, max_age_seconds: int = 120, required_bookmakers: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Recupera o snapshot se ainda estiver fresco e cobrir os bookmakers necessários.

        - max_age_seconds: idade máxima do snapshot em segundos
        - required_bookmakers: se fornecido, a lista exigida deve ser subconjunto do snapshot
        """
        try:
            with self.get_connection() as conn:
                row = conn.execute(
                    "SELECT response_json, created_at FROM api_cache WHERE cache_key = ?",
                    (self.CACHE_KEY,),
                ).fetchone()

            if not row:
                return None

            # Verifica frescor pela coluna created_at
            created_at_str = row["created_at"]
            try:
                created_at = datetime.fromisoformat(str(created_at_str))
            except Exception:
                # Se não conseguir parsear, considera expirado
                return None

            now = datetime.now(timezone.utc)
            # Se created_at vier sem tz, assume UTC
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            age = (now - created_at).total_seconds()
            if max_age_seconds is not None and age > max_age_seconds:
                return None

            # Carrega o conteúdo salvo
            payload = json.loads(row["response_json"] or "{}")
            snapshot_bookmakers = [str(b).strip() for b in (payload.get("bookmakers") or []) if str(b).strip()]

            # Checagem de cobertura de bookmakers
            if required_bookmakers:
                req_norm = {str(b).strip() for b in required_bookmakers if str(b).strip()}
                snap_norm = set(snapshot_bookmakers)
                if not req_norm.issubset(snap_norm):
                    return None

            return {
                "bookmakers": snapshot_bookmakers,
                "timestamp": payload.get("timestamp") or created_at.isoformat(),
                "eventos": payload.get("eventos") or [],
            }

        except Exception:
            # Qualquer erro: prefere não bloquear o fluxo; retorna None
            return None


_global_snapshot_cache_instance: Optional[GlobalSnapshotCache] = None


def get_snapshot_cache() -> GlobalSnapshotCache:
    global _global_snapshot_cache_instance
    if _global_snapshot_cache_instance is None:
        _global_snapshot_cache_instance = GlobalSnapshotCache()
    return _global_snapshot_cache_instance
