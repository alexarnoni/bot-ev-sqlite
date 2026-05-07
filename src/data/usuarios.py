"""
Sistema de gerenciamento de usuários
"""
from typing import List, Dict, Optional
from src.core.database import get_db

class UserManager:
    def __init__(self):
        self.db = get_db()
    
    def create_or_update_user(self, chat_id: int, nome: str = None, username: str = None):
        """Cria ou atualiza um usuário"""
        self.db.create_or_update_user(chat_id, nome, username)
    
    def get_user(self, chat_id: int) -> Optional[Dict]:
        """Retorna dados de um usuário"""
        return self.db.get_user(chat_id)
    
    def get_user_complete(self, chat_id: int) -> Dict:
        """Retorna usuário com todos os filtros"""
        return self.db.get_user_complete(chat_id)
    
    def usuario_configurado(self, chat_id: int) -> bool:
        """Verifica se usuário está configurado"""
        return self.db.usuario_configurado(chat_id)
    
    def delete_user(self, chat_id: int):
        """Remove um usuário"""
        self.db.delete_user(chat_id)
    
    def block_user(self, chat_id: int):
        """Bloqueia um usuário administrativamente"""
        self.db.block_user(chat_id)
    
    def unblock_user(self, chat_id: int):
        """Remove bloqueio de um usuário"""
        self.db.unblock_user(chat_id)
    
    def is_user_blocked(self, chat_id: int) -> bool:
        """Verifica se usuário está bloqueado"""
        return self.db.is_user_blocked(chat_id)
    
    def get_all_users(self) -> List[Dict]:
        """Retorna todos os usuários ativos"""
        return self.db.get_all_users()
    
    def set_user_bookmakers(self, chat_id: int, bookmakers: List[str]):
        """Define bookmakers de um usuário"""
        self.db.set_user_bookmakers(chat_id, bookmakers)
    
    def get_user_bookmakers(self, chat_id: int) -> List[str]:
        """Retorna bookmakers de um usuário"""
        return self.db.get_user_bookmakers(chat_id)
    
    def set_user_filter(self, chat_id: int, **kwargs):
        """Define filtros de um usuário"""
        self.db.set_user_filter(chat_id, **kwargs)
    
    def get_user_filter(self, chat_id: int) -> Dict:
        """Retorna filtros de um usuário"""
        return self.db.get_user_filter(chat_id)
    
    def set_user_leagues(self, chat_id: int, leagues: Optional[List[str]]):
        """Define ligas de um usuário"""
        self.db.set_user_leagues(chat_id, leagues)
    
    def get_user_leagues(self, chat_id: int) -> Optional[List[str]]:
        """Retorna ligas de um usuário"""
        return self.db.get_user_leagues(chat_id)
    
    def set_user_sports(self, chat_id: int, sports: Optional[List[str]]):
        """Define esportes de um usuário"""
        self.db.set_user_sports(chat_id, sports)
    
    def get_user_sports(self, chat_id: int) -> Optional[List[str]]:
        """Retorna esportes de um usuário"""
        return self.db.get_user_sports(chat_id)
    
    def get_users_with_bookmakers(self, bookmakers: List[str]) -> List[int]:
        """Retorna usuários que usam os bookmakers especificados"""
        all_users = self.get_all_users()
        matching_users = []
        
        for user in all_users:
            user_bookmakers = self.get_user_bookmakers(user['chat_id'])
            if any(bk in user_bookmakers for bk in bookmakers):
                matching_users.append(user['chat_id'])
        
        return matching_users

# Singleton global
_user_manager_instance = None

def get_user_manager() -> UserManager:
    """Retorna instância singleton do gerenciador de usuários"""
    global _user_manager_instance
    if _user_manager_instance is None:
        _user_manager_instance = UserManager()
    return _user_manager_instance
