"""
Configuração de bookmakers - verifica se usuário está configurado
"""
import asyncio
from database import get_db
import os

# Configuração do banco de dados
def get_database_path():
    feed_id = os.getenv("FEED_ID", "default")
    return os.path.join(os.getcwd(), "data", feed_id, "bot.db")


def usuario_configurado(chat_id: int) -> bool:
    """
    Verifica se o usuário está completamente configurado usando Database.
    Requer existir registro em user_filters e ao menos um bookmaker em user_bookmakers.
    """
    try:
        db = get_db()
        return db.usuario_configurado(int(chat_id))
    except Exception as e:
        print(f"Erro ao verificar configuração do usuário {chat_id}: {e}")
        return False
