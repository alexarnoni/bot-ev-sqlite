"""
Configuração de bookmakers - fonte única da verdade
"""
import asyncio
from database import get_db
import os

# ===========================================
# CONFIGURAÇÃO DE BOOKMAKERS
# ===========================================

BOOKMAKERS_ATIVOS = [
    "Bet365",
    "BetMGM",
    "Betano",
    "Betfair Sportsbook",
    "Novibet",
    "Superbet",
]

BOOKMAKER_ALIASES = {
    "bet365": "Bet365",
    "bet mgm": "BetMGM",
    "betmgm": "BetMGM",
    "mgm": "BetMGM",
    "betano": "Betano",
    "betfair": "Betfair Sportsbook",
    "betfair sportsbook": "Betfair Sportsbook",
    "novibet": "Novibet",
    "superbet": "Superbet",
}

def canonical_bookmaker(name: str) -> str:
    """Converte nome do bookmaker para formato canônico"""
    if not name:
        return ""
    key = str(name).strip().lower()
    return BOOKMAKER_ALIASES.get(key, name.strip())

def is_supported_bookmaker(name: str) -> bool:
    """Verifica se o bookmaker é suportado"""
    return canonical_bookmaker(name) in BOOKMAKERS_ATIVOS

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
