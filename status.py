"""
Status do sistema - verifica status da API e sistema
"""
import asyncio
import aiohttp
import logging
from typing import Dict, Any
from config import ODDS_API_KEY, ODDS_API_BASE

logger = logging.getLogger(__name__)

async def get_odds_api_status() -> bool:
    """
    Verifica se a API Odds está online
    """
    try:
        url = f"{ODDS_API_BASE}/sports"
        params = {"apiKey": ODDS_API_KEY}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return len(data) > 0
                else:
                    logger.warning(f"API retornou status {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"Erro ao verificar status da API: {e}")
        return False

async def get_system_status() -> Dict[str, Any]:
    """
    Retorna status completo do sistema
    """
    try:
        # Status da API
        api_online = await get_odds_api_status()
        
        # Status do banco de dados
        try:
            from database import SQLiteConnectionPool, SQLiteConnectionConfig
            import os
            
            db_config = SQLiteConnectionConfig(
                database_path=os.path.join(os.getcwd(), "data", "bot.db"),
                max_connections=10,
                timeout=30.0
            )
            db_pool = SQLiteConnectionPool(db_config)
            
            async with db_pool.get_connection() as conn:
                cursor = await conn.execute("SELECT COUNT(*) as count FROM users WHERE is_active = 1")
                users_count = (await cursor.fetchone())['count']
                
                cursor = await conn.execute("SELECT COUNT(*) as count FROM alert_history WHERE DATE(created_at) = DATE('now')")
                alerts_today = (await cursor.fetchone())['count']
            
            db_online = True
            
        except Exception as e:
            logger.error(f"Erro ao verificar banco de dados: {e}")
            db_online = False
            users_count = 0
            alerts_today = 0
        
        # Status do rate limiter
        try:
            from rate_limiter import api_rate_limiter
            requests_count = await api_rate_limiter.get_requests_count()
        except Exception as e:
            logger.error(f"Erro ao verificar rate limiter: {e}")
            requests_count = 0
        
        return {
            "api_online": api_online,
            "database_online": db_online,
            "active_users": users_count,
            "alerts_today": alerts_today,
            "requests_last_hour": requests_count,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter status do sistema: {e}")
        return {
            "api_online": False,
            "database_online": False,
            "active_users": 0,
            "alerts_today": 0,
            "requests_last_hour": 0,
            "timestamp": 0
        }

# Singleton global
_status_instance = None

def get_status():
    """Retorna instância singleton do status"""
    global _status_instance
    if _status_instance is None:
        _status_instance = StatusManager()
    return _status_instance

class StatusManager:
    """Gerenciador de status do sistema"""
    
    def __init__(self):
        pass
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Retorna status completo do sistema"""
        return await get_system_status()
    
    async def get_odds_api_status(self) -> bool:
        """Verifica se a API Odds está online"""
        return await get_odds_api_status()