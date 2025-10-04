"""
Sistema de cache de alertas para evitar duplicatas
"""
from typing import Set
from database import get_db, generate_alert_hash

class AlertCache:
    def __init__(self):
        self.db = get_db()
    
    def add_alert(self, chat_id: int, evento: dict):
        """Adiciona alerta ao cache"""
        alert_hash = generate_alert_hash(evento)
        self.db.add_to_cache(chat_id, alert_hash)
    
    def is_duplicate(self, chat_id: int, evento: dict) -> bool:
        """Verifica se alerta já foi enviado"""
        alert_hash = generate_alert_hash(evento)
        return self.db.is_in_cache(chat_id, alert_hash)
    
    def get_user_cache(self, chat_id: int) -> Set[str]:
        """Retorna cache de um usuário"""
        return self.db.get_cache_hashes(chat_id)
    
    def clean_old_cache(self, days: int = 30):
        """Limpa cache antigo"""
        self.db.clean_old_cache(days)

# Singleton global
_cache_instance = None

def get_cache() -> AlertCache:
    """Retorna instância singleton do cache"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = AlertCache()
    return _cache_instance
