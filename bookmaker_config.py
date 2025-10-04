"""
Configuração de bookmakers - verifica se usuário está configurado
"""
import asyncio
from database import SQLiteConnectionPool, SQLiteConnectionConfig
from config import get_telegram_token, FEED_ID
import os

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

async def usuario_configurado(chat_id: int) -> bool:
    """
    Verifica se o usuário está completamente configurado
    """
    try:
        async with db_pool.get_connection() as conn:
            # Verifica se tem filtros
            cursor = await conn.execute("""
                SELECT COUNT(*) as count FROM user_filters WHERE chat_id = ?
            """, (chat_id,))
            tem_filtros = (await cursor.fetchone())['count'] > 0
            
            # Verifica se tem ligas
            cursor = await conn.execute("""
                SELECT COUNT(*) as count FROM user_leagues WHERE chat_id = ?
            """, (chat_id,))
            tem_ligas = (await cursor.fetchone())['count'] > 0
            
            # Verifica se tem esportes
            cursor = await conn.execute("""
                SELECT COUNT(*) as count FROM user_sports WHERE chat_id = ?
            """, (chat_id,))
            tem_esportes = (await cursor.fetchone())['count'] > 0
            
            # Verifica se tem bookmakers
            cursor = await conn.execute("""
                SELECT COUNT(*) as count FROM user_bookmakers WHERE chat_id = ?
            """, (chat_id,))
            tem_bookmakers = (await cursor.fetchone())['count'] > 0
            
            # Usuário está configurado se tem todas as configurações
            return tem_filtros and tem_ligas and tem_esportes and tem_bookmakers
            
    except Exception as e:
        print(f"Erro ao verificar configuração do usuário {chat_id}: {e}")
        return False
