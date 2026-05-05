"""
Módulo de banco de dados SQLite para o Bot EV+
"""
import sqlite3
import json
import hashlib
from datetime import datetime, timezone
from contextlib import contextmanager, asynccontextmanager
from typing import Optional, List, Dict, Set, Any
from config import feed_path, FEED_ID

class DatabaseError(Exception):
    """Exceção personalizada para erros de banco de dados"""
    pass

class Database:
    def __init__(self, feed_id: str = None):
        if feed_id is None:
            feed_id = FEED_ID
        self.feed_id = feed_id
        self.db_path = feed_path("bot.db", feed_id)
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager para conexões com o banco"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # PRAGMAs para estabilidade e desempenho em concorrência
        conn.execute("PRAGMA foreign_keys = ON")
        # Modo WAL melhora concorrência entre leitores/escritores
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        # Reduz fsync agressivo mantendo segurança adequada para app
        try:
            conn.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass
        # Evita erros rápidos de lock sob concorrência
        try:
            conn.execute("PRAGMA busy_timeout=5000")
        except Exception:
            pass
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Cria todas as tabelas do banco"""
        with self.get_connection() as conn:
            # 1. Tabela users
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    nome TEXT,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    is_blocked BOOLEAN DEFAULT 0
                )
            """)
            # Adicionar coluna is_blocked se não existir (migration)
            try:
                conn.execute("ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT 0")
            except Exception:
                pass  # Coluna já existe
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(is_blocked)")
            
            # 2. Tabela user_bookmakers
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_bookmakers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    bookmaker TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES users(chat_id) ON DELETE CASCADE,
                    UNIQUE(chat_id, bookmaker)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_bookmakers_chat ON user_bookmakers(chat_id)")
            
            # 3. Tabela user_filters
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_filters (
                    chat_id INTEGER PRIMARY KEY,
                    ev_faixa_min REAL DEFAULT 0.05,
                    ev_faixa_max REAL,
                    data_inicio DATE,
                    data_fim DATE,
                    filtro_dias INTEGER,
                    horario_inicio TIME,
                    horario_fim TIME,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES users(chat_id) ON DELETE CASCADE
                )
            """)
            
            # 4. Tabela user_leagues
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_leagues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    league TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES users(chat_id) ON DELETE CASCADE,
                    UNIQUE(chat_id, league)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_leagues_chat ON user_leagues(chat_id)")
            
            # 5. Tabela user_sports
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_sports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    sport TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES users(chat_id) ON DELETE CASCADE,
                    UNIQUE(chat_id, sport)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sports_chat ON user_sports(chat_id)")
            
            # 6. Tabela alert_cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    alert_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES users(chat_id) ON DELETE CASCADE,
                    UNIQUE(chat_id, alert_hash)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_cache_chat ON alert_cache(chat_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_cache_hash ON alert_cache(alert_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_cache_created ON alert_cache(created_at)")
            # Índice composto para otimizar a query mais frequente: WHERE chat_id = ? AND alert_hash = ?
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_cache_composite ON alert_cache(chat_id, alert_hash)")
            
            # 7. Tabela alert_history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    data_envio TIMESTAMP NOT NULL,
                    alert_hash TEXT,
                    esporte TEXT,
                    home TEXT,
                    away TEXT,
                    mercado TEXT,
                    odd REAL,
                    stake REAL,
                    ev REAL,
                    data_jogo TIMESTAMP,
                    url_bet TEXT,
                    bookmaker TEXT,
                    FOREIGN KEY (chat_id) REFERENCES users(chat_id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_chat ON alert_history(chat_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_date ON alert_history(data_envio)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_ev ON alert_history(ev)")
            # Índice composto para ordenação por usuário+data e dedup por hash
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_chat_time ON alert_history(chat_id, data_envio DESC)")
            except Exception:
                pass
            try:
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_history_chat_hash ON alert_history(chat_id, alert_hash)")
            except Exception:
                pass
            
            # 8. Tabela pending_alerts
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    evento JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chat_id) REFERENCES users(chat_id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_chat ON pending_alerts(chat_id)")
            
            # 9. Tabela league_catalog
            conn.execute("""
                CREATE TABLE IF NOT EXISTS league_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    region TEXT NOT NULL,
                    sport TEXT NOT NULL,
                    league TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(region, sport, league)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_catalog_region ON league_catalog(region)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_catalog_sport ON league_catalog(sport)")
            
            # 10. Tabela system_status
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_status (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    odds_api_ok BOOLEAN DEFAULT 1,
                    odds_api_message TEXT,
                    odds_api_details TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Inserir registro inicial se não existir
            conn.execute("INSERT OR IGNORE INTO system_status (id) VALUES (1)")
            
            # 11. Tabela rate_limiter
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limiter (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_limiter_ts ON rate_limiter(request_timestamp)")

            # 12. Tabela api_cache (compatibilidade com versões antigas)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    response_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
    # === USERS ===
    def create_or_update_user(self, chat_id: int, nome: str = None, username: str = None):
        """Cria ou atualiza um usuário"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO users (chat_id, nome, username) 
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    nome = COALESCE(excluded.nome, nome),
                    username = COALESCE(excluded.username, username),
                    updated_at = CURRENT_TIMESTAMP
            """, (chat_id, nome, username))
    
    def get_user(self, chat_id: int) -> Optional[Dict]:
        """Retorna dados de um usuário"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
            return dict(row) if row else None
    
    def delete_user(self, chat_id: int):
        """Remove um usuário e todos os dados relacionados"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))
    
    def block_user(self, chat_id: int):
        """Bloqueia um usuário administrativamente"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE users SET is_blocked = 1, updated_at = CURRENT_TIMESTAMP 
                WHERE chat_id = ?
            """, (chat_id,))
    
    def unblock_user(self, chat_id: int):
        """Remove bloqueio administrativo de um usuário"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE users SET is_blocked = 0, updated_at = CURRENT_TIMESTAMP 
                WHERE chat_id = ?
            """, (chat_id,))
    
    def is_user_blocked(self, chat_id: int) -> bool:
        """Verifica se usuário está bloqueado"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT is_blocked FROM users WHERE chat_id = ?", 
                (chat_id,)
            ).fetchone()
            return bool(row['is_blocked']) if row else False
    
    def usuario_configurado(self, chat_id: int) -> bool:
        """Verifica se o usuário tem configuração completa"""
        with self.get_connection() as conn:
            # Verifica se tem filtros e pelo menos um bookmaker
            row = conn.execute("""
                SELECT 1 FROM user_filters uf
                JOIN user_bookmakers ub ON uf.chat_id = ub.chat_id
                WHERE uf.chat_id = ?
                LIMIT 1
            """, (chat_id,)).fetchone()
            return row is not None
    
    # === BOOKMAKERS ===
    def set_user_bookmakers(self, chat_id: int, bookmakers: List[str]):
        """Define os bookmakers de um usuário"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM user_bookmakers WHERE chat_id = ?", (chat_id,))
            for bk in bookmakers:
                conn.execute(
                    "INSERT INTO user_bookmakers (chat_id, bookmaker) VALUES (?, ?)",
                    (chat_id, bk)
                )
    
    def get_user_bookmakers(self, chat_id: int) -> List[str]:
        """Retorna os bookmakers de um usuário"""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT bookmaker FROM user_bookmakers WHERE chat_id = ?",
                (chat_id,)
            ).fetchall()
            return [row['bookmaker'] for row in rows]
    
    # === FILTERS ===
    def set_user_filter(self, chat_id: int, **kwargs):
        """Define filtros de um usuário"""
        with self.get_connection() as conn:
            # Cria se não existe
            conn.execute("""
                INSERT INTO user_filters (chat_id) VALUES (?)
                ON CONFLICT(chat_id) DO NOTHING
            """, (chat_id,))
            
            # Update campos fornecidos
            fields = []
            values = []
            for key, value in kwargs.items():
                if value is not None:
                    fields.append(f"{key} = ?")
                    values.append(value)
            
            if fields:
                values.append(chat_id)
                query = f"UPDATE user_filters SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?"
                conn.execute(query, values)
    
    def get_user_filter(self, chat_id: int) -> Dict:
        """Retorna filtros de um usuário"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM user_filters WHERE chat_id = ?", (chat_id,)).fetchone()
            return dict(row) if row else {}
    
    # === LIGAS/ESPORTES ===
    def set_user_leagues(self, chat_id: int, leagues: Optional[List[str]]):
        """Define ligas de um usuário"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM user_leagues WHERE chat_id = ?", (chat_id,))
            if leagues:
                for league in leagues:
                    conn.execute(
                        "INSERT INTO user_leagues (chat_id, league) VALUES (?, ?)",
                        (chat_id, league)
                    )
    
    def get_user_leagues(self, chat_id: int) -> List[List[str]]:
        """Retorna ligas de um usuário. Sempre retorna lista (possivelmente vazia)."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT league FROM user_leagues WHERE chat_id = ?",
                (chat_id,)
            ).fetchall()
            result = [row['league'] for row in rows]
            return result
    
    def set_user_sports(self, chat_id: int, sports: Optional[List[str]]):
        """Define esportes de um usuário"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM user_sports WHERE chat_id = ?", (chat_id,))
            if sports:
                for sport in sports:
                    conn.execute(
                        "INSERT INTO user_sports (chat_id, sport) VALUES (?, ?)",
                        (chat_id, sport)
                    )
    
    def get_user_sports(self, chat_id: int) -> List[str]:
        """Retorna esportes de um usuário. Sempre retorna lista (possivelmente vazia)."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT sport FROM user_sports WHERE chat_id = ?",
                (chat_id,)
            ).fetchall()
            result = [row['sport'] for row in rows]
            return result
    
    # === CACHE ===
    def add_to_cache(self, chat_id: int, alert_hash: str):
        """Adiciona hash ao cache de alertas"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO alert_cache (chat_id, alert_hash)
                VALUES (?, ?)
            """, (chat_id, alert_hash))
    
    def is_in_cache(self, chat_id: int, alert_hash: str) -> bool:
        """Verifica se hash está no cache"""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT 1 FROM alert_cache 
                WHERE chat_id = ? AND alert_hash = ?
            """, (chat_id, alert_hash)).fetchone()
            return row is not None
    
    def get_cache_hashes(self, chat_id: int) -> Set[str]:
        """Retorna todos os hashes do cache de um usuário"""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT alert_hash FROM alert_cache WHERE chat_id = ?",
                (chat_id,)
            ).fetchall()
            return {row['alert_hash'] for row in rows}
    
    def clean_old_cache(self, days: int = 30):
        """Limpa cache mais antigo que X dias"""
        with self.get_connection() as conn:
            conn.execute("""
                DELETE FROM alert_cache 
                WHERE created_at < datetime('now', '-' || ? || ' days')
            """, (days,))
    
    # === HISTÓRICO ===
    def add_alert_history(self, chat_id: int, **kwargs):
        """Adiciona alerta ao histórico"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO alert_history 
                (chat_id, data_envio, alert_hash, esporte, home, away, mercado, 
                 odd, stake, ev, data_jogo, url_bet, bookmaker)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chat_id,
                kwargs.get('data_envio'),
                kwargs.get('alert_hash'),
                kwargs.get('esporte'),
                kwargs.get('home'),
                kwargs.get('away'),
                kwargs.get('mercado'),
                kwargs.get('odd'),
                kwargs.get('stake'),
                kwargs.get('ev'),
                kwargs.get('data_jogo'),
                kwargs.get('url_bet'),
                kwargs.get('bookmaker')
            ))
    
    def get_user_history(self, chat_id: int, limit: int = 100) -> List[Dict]:
        """Retorna histórico de alertas de um usuário"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM alert_history 
                WHERE chat_id = ? 
                ORDER BY data_envio DESC 
                LIMIT ?
            """, (chat_id, limit)).fetchall()
            return [dict(row) for row in rows]
    
    def get_user_stats(self, chat_id: int) -> Dict:
        """Retorna estatísticas de um usuário"""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total_alertas,
                    AVG(ev) as ev_medio,
                    MIN(data_envio) as primeiro_alerta,
                    MAX(data_envio) as ultimo_alerta
                FROM alert_history
                WHERE chat_id = ?
            """, (chat_id,)).fetchone()
            return dict(row) if row else {}

    def count_user_alerts(self, chat_id: int) -> int:
        """Conta alertas do usuário (últimos N não filtrados por data)"""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as total FROM alert_history WHERE chat_id = ?
            """, (chat_id,)).fetchone()
            return int(row['total']) if row else 0

    def count_alerts_on_date(self, target_date: datetime.date) -> int:
        """Conta alertas no dia informado considerando data_envio"""
        from datetime import datetime, timedelta
        inicio = datetime.combine(target_date, datetime.min.time())
        fim = inicio + timedelta(days=1)
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as total
                FROM alert_history
                WHERE data_envio >= ? AND data_envio < ?
            """, (inicio.isoformat(sep=" "), fim.isoformat(sep=" "))).fetchone()
            return int(row['total']) if row else 0

    def count_api_cache_entries(self) -> int:
        """Conta entradas na tabela api_cache"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as total FROM api_cache").fetchone()
            return int(row['total']) if row else 0
    
    # === PENDENTES ===
    def add_pending_alert(self, chat_id: int, evento: Dict):
        """Adiciona alerta pendente"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO pending_alerts (chat_id, evento)
                VALUES (?, ?)
            """, (chat_id, json.dumps(evento)))
    
    def get_pending_alerts(self, chat_id: int) -> List[Dict]:
        """Retorna alertas pendentes de um usuário"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT evento FROM pending_alerts WHERE chat_id = ?
            """, (chat_id,)).fetchall()
            return [json.loads(row['evento']) for row in rows]
    
    def clear_pending_alerts(self, chat_id: int):
        """Remove todos os alertas pendentes de um usuário"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM pending_alerts WHERE chat_id = ?", (chat_id,))
    
    # === CATÁLOGO DE LIGAS ===
    def update_league_catalog(self, catalog: Dict[str, Dict[str, List[str]]]):
        """Atualiza catálogo de ligas"""
        with self.get_connection() as conn:
            for region, sports in catalog.items():
                for sport, leagues in sports.items():
                    for league in leagues:
                        conn.execute("""
                            INSERT INTO league_catalog (region, sport, league)
                            VALUES (?, ?, ?)
                            ON CONFLICT(region, sport, league) DO UPDATE SET
                                updated_at = CURRENT_TIMESTAMP
                        """, (region, sport, league))
    
    def get_league_catalog(self) -> Dict[str, Dict[str, List[str]]]:
        """Retorna catálogo de ligas"""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM league_catalog").fetchall()
            
        catalog = {}
        for row in rows:
            region = row['region']
            sport = row['sport']
            league = row['league']
            
            if region not in catalog:
                catalog[region] = {}
            if sport not in catalog[region]:
                catalog[region][sport] = []
            catalog[region][sport].append(league)
        
        return catalog
    
    # === SISTEMA ===
    def set_api_status(self, ok: bool, message: str, details: str = None):
        """Atualiza status da API"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE system_status SET
                    odds_api_ok = ?,
                    odds_api_message = ?,
                    odds_api_details = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (ok, message, details))
    
    def get_api_status(self) -> Dict:
        """Retorna status da API"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM system_status WHERE id = 1").fetchone()
            return dict(row) if row else {}
    
    # === RATE LIMITER ===
    def add_request_log(self):
        """Registra uma requisição para rate limiting"""
        with self.get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT INTO rate_limiter (request_timestamp) VALUES (?)
            """, (now,))
    
    def get_request_count_last_hour(self) -> int:
        """Retorna número de requisições na última hora"""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as count FROM rate_limiter
                WHERE request_timestamp >= datetime('now', '-1 hour')
            """).fetchone()
            return row['count'] if row else 0
    
    def clean_old_request_logs(self):
        """Limpa logs de requisições antigos"""
        with self.get_connection() as conn:
            conn.execute("""
                DELETE FROM rate_limiter 
                WHERE request_timestamp < datetime('now', '-2 hours')
            """)
    
    def clean_old_history(self, days: int = 90):
        """Limpa histórico de alertas antigos"""
        with self.get_connection() as conn:
            conn.execute("""
                DELETE FROM alert_history 
                WHERE data_envio < datetime('now', '-' || ? || ' days')
            """, (days,))
    
    def clean_old_pending_alerts(self, hours: int = 24):
        """Limpa alertas pendentes antigos"""
        with self.get_connection() as conn:
            conn.execute("""
                DELETE FROM pending_alerts 
                WHERE created_at < datetime('now', '-' || ? || ' hours')
            """, (hours,))
    
    # === ADMIN ===
    def get_all_users(self) -> List[Dict]:
        """Retorna todos os usuários ativos com estatísticas"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT u.*, 
                       u.is_blocked,
                       COUNT(DISTINCT ub.bookmaker) as num_bookmakers,
                       COUNT(DISTINCT ah.id) as total_alertas
                FROM users u
                LEFT JOIN user_bookmakers ub ON u.chat_id = ub.chat_id
                LEFT JOIN alert_history ah ON u.chat_id = ah.chat_id
                WHERE u.is_active = 1
                GROUP BY u.chat_id
            """).fetchall()
            return [dict(row) for row in rows]
    
    def get_system_stats(self) -> Dict:
        """Retorna estatísticas do sistema"""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT 
                    COUNT(DISTINCT chat_id) as usuarios_ativos,
                    COUNT(*) as total_alertas,
                    AVG(ev) as ev_medio
                FROM alert_history
                WHERE data_envio >= datetime('now', '-24 hours')
            """).fetchone()
            return dict(row) if row else {}
    
    # === HELPER: GET USER COMPLETO ===
    def get_user_complete(self, chat_id: int) -> Dict:
        """Retorna user com todos os filtros - compatível com JSON antigo"""
        user = self.get_user(chat_id)
        if not user:
            return {}
        
        filters = self.get_user_filter(chat_id)
        bookmakers = self.get_user_bookmakers(chat_id)
        leagues = self.get_user_leagues(chat_id) or []
        sports = self.get_user_sports(chat_id) or []
        
        return {
            'nome': user.get('nome'),
            'username': user.get('username'),
            'bookmakers': bookmakers,
            **filters,
            'ligas': leagues or [],
            'esportes': sports or []
        }

# Singleton global
_db_instance = None

def get_db() -> Database:
    """Retorna instância singleton do banco"""
    global _db_instance
    if _db_instance is None:
        from config import FEED_ID
        _db_instance = Database(FEED_ID)
    return _db_instance

# Classes para conexão assíncrona
import asyncio
import aiosqlite
from contextlib import asynccontextmanager

class SQLiteConnectionConfig:
    """Configuração para pool de conexões SQLite"""
    def __init__(self, database_path: str, max_connections: int = 10, timeout: float = 30.0):
        self.database_path = database_path
        self.max_connections = max_connections
        self.timeout = timeout

class SQLiteConnectionPool:
    """Pool de conexões SQLite assíncronas"""
    def __init__(self, config: SQLiteConnectionConfig):
        self.config = config
        self._pool = asyncio.Queue(maxsize=config.max_connections)
        self._created_connections = 0
        self._lock = asyncio.Lock()
    
    async def _get_connection(self):
        """Retorna uma conexão do pool"""
        try:
            # Tenta pegar conexão existente
            conn = self._pool.get_nowait()
            return conn
        except asyncio.QueueEmpty:
            # Cria nova conexão se possível
            async with self._lock:
                if self._created_connections < self.config.max_connections:
                    conn = await aiosqlite.connect(
                        self.config.database_path,
                        timeout=self.config.timeout
                    )
                    conn.row_factory = aiosqlite.Row
                    # PRAGMAs para conexões assíncronas
                    await conn.execute("PRAGMA foreign_keys = ON")
                    try:
                        await conn.execute("PRAGMA journal_mode=WAL")
                    except Exception:
                        pass
                    try:
                        await conn.execute("PRAGMA synchronous=NORMAL")
                    except Exception:
                        pass
                    try:
                        await conn.execute("PRAGMA busy_timeout=5000")
                    except Exception:
                        pass
                    self._created_connections += 1
                    return conn
                else:
                    # Aguarda conexão disponível
                    conn = await self._pool.get()
                    return conn
    
    async def return_connection(self, conn):
        """Retorna conexão para o pool"""
        try:
            self._pool.put_nowait(conn)
        except asyncio.QueueFull:
            # Pool cheio, fecha a conexão
            await conn.close()
            async with self._lock:
                self._created_connections -= 1
    
    async def close_all(self):
        """Fecha todas as conexões do pool"""
        while not self._pool.empty():
            conn = await self._pool.get()
            await conn.close()
        self._created_connections = 0
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager para conexões"""
        conn = await self._get_connection()
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await self.return_connection(conn)

def generate_alert_hash(evento: Dict) -> str:
    """Gera hash único para um alerta"""
    # Usa id, market e odd para gerar hash único
    hash_string = f"{evento.get('id', '')}|{evento.get('market_name', '')}|{evento.get('bet365_odds', '')}"
    return hashlib.sha256(hash_string.encode()).hexdigest()
