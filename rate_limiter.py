"""
Rate Limiter - controla limite de requests para a API
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from database import SQLiteConnectionPool, SQLiteConnectionConfig
from config import RATE_LIMIT_REQUESTS_PER_HOUR
import os

logger = logging.getLogger(__name__)

# Configuração do banco de dados
def get_database_path():
    feed_id = os.getenv("FEED_ID", "default")
    return os.path.join(os.getcwd(), "data", feed_id, "bot.db")

db_config = SQLiteConnectionConfig(
    database_path=get_database_path(),
    max_connections=10,
    timeout=30.0
)
db_pool = SQLiteConnectionPool(db_config)

class APIRateLimiter:
    def __init__(self, max_requests_per_hour: int = RATE_LIMIT_REQUESTS_PER_HOUR):
        self.max_requests = max_requests_per_hour
        self.db_pool = db_pool

    async def can_make_request(self) -> bool:
        """
        Verifica se pode fazer uma nova request
        """
        try:
            requests_count = await self.get_requests_count()
            return requests_count < self.max_requests
            
        except Exception as e:
            logger.error(f"Erro ao verificar rate limit: {e}")
            return False

    async def log_request(self):
        """
        Registra uma nova request
        """
        try:
            async with self.db_pool.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO rate_limiter (request_timestamp, created_at)
                    VALUES (datetime('now'), datetime('now'))
                """)
                
        except Exception as e:
            logger.error(f"Erro ao registrar request: {e}")

    async def get_requests_count(self) -> int:
        """
        Retorna número de requests na última hora
        """
        try:
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT COUNT(*) as count FROM rate_limiter 
                    WHERE request_timestamp >= datetime('now', '-1 hour')
                """)
                
                result = await cursor.fetchone()
                return result['count'] if result else 0
                
        except Exception as e:
            logger.error(f"Erro ao contar requests: {e}")
            return 0

    async def cleanup_old_requests(self):
        """
        Remove requests antigas (mais de 24 horas)
        """
        try:
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    DELETE FROM rate_limiter 
                    WHERE request_timestamp < datetime('now', '-24 hours')
                """)
                
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"Removidas {deleted_count} requests antigas")
                    
        except Exception as e:
            logger.error(f"Erro na limpeza de requests: {e}")

    async def get_remaining_requests(self) -> int:
        """
        Retorna número de requests restantes na hora atual
        """
        try:
            current_requests = await self.get_requests_count()
            return max(0, self.max_requests - current_requests)
            
        except Exception as e:
            logger.error(f"Erro ao calcular requests restantes: {e}")
            return 0

    def get_stats(self) -> dict:
        """
        Retorna estatísticas do rate limiter de forma síncrona
        """
        try:
            # Usar o método síncrono do database para evitar problemas de async
            from database import get_db
            db = get_db()
            
            requests_used = db.get_request_count_last_hour()
            requests_remaining = max(0, self.max_requests - requests_used)
            usage_percent = (requests_used / self.max_requests) * 100 if self.max_requests > 0 else 0
            
            return {
                'requests_used': requests_used,
                'requests_max': self.max_requests,
                'requests_remaining': requests_remaining,
                'usage_percent': usage_percent
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas do rate limiter: {e}")
            return {
                'requests_used': 0,
                'requests_max': self.max_requests,
                'requests_remaining': self.max_requests,
                'usage_percent': 0.0
            }

    async def get_reset_time(self) -> Optional[datetime]:
        """
        Retorna quando o rate limit será resetado
        """
        try:
            async with self.db_pool.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT MIN(request_timestamp) as first_request 
                    FROM rate_limiter 
                    WHERE request_timestamp >= datetime('now', '-1 hour')
                """)
                
                result = await cursor.fetchone()
                if result and result['first_request']:
                    first_request = datetime.fromisoformat(result['first_request'])
                    reset_time = first_request + timedelta(hours=1)
                    return reset_time
                    
            return None
            
        except Exception as e:
            logger.error(f"Erro ao calcular reset time: {e}")
            return None

# Instância global do rate limiter
api_rate_limiter = APIRateLimiter()

def get_rate_limiter() -> APIRateLimiter:
    """Retorna instância singleton do rate limiter"""
    return api_rate_limiter