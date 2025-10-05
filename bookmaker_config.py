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

def usuario_configurado(chat_id: int) -> bool:
    """
    Verifica se o usuário está completamente configurado
    """
    try:
        import sqlite3
        db_path = get_database_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Verifica se tem filtros básicos
        cursor = conn.execute("""
            SELECT filter_data FROM users WHERE chat_id = ?
        """, (str(chat_id),))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row['filter_data']:
            return False
        
        import json
        filtros = json.loads(row['filter_data'])
        
        # Verifica configurações mínimas
        tem_bookmakers = bool(filtros.get("bookmakers"))
        tem_ev_min = filtros.get("ev_faixa_min") is not None
        
        return tem_bookmakers and tem_ev_min
            
    except Exception as e:
        print(f"Erro ao verificar configuração do usuário {chat_id}: {e}")
        return False
