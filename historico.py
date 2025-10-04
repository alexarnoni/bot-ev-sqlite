"""
Sistema de histórico de alertas
"""
from datetime import datetime
from typing import List, Dict
from database import get_db

class AlertHistory:
    def __init__(self):
        self.db = get_db()
    
    def add_alert(self, chat_id: int, evento: dict, stake: float):
        """Adiciona alerta ao histórico"""
        try:
            # Formata dados do evento
            data_envio = datetime.now().strftime("%d/%m/%Y %H:%M")
            data_jogo = evento.get("commence_time", "")
            
            # Converte data do jogo se necessário
            if data_jogo and 'T' in data_jogo:
                try:
                    dt = datetime.fromisoformat(data_jogo.replace('Z', '+00:00'))
                    data_jogo = dt.strftime("%d/%m/%Y %H:%M")
                except:
                    data_jogo = data_jogo
            
            self.db.add_alert_history(
                chat_id=chat_id,
                data_envio=data_envio,
                esporte=evento.get("sport", ""),
                home=evento.get("home", ""),
                away=evento.get("away", ""),
                mercado=evento.get("market_name", ""),
                odd=evento.get("bet365_odds", 0),
                stake=stake,
                ev=evento.get("ev", 0),
                data_jogo=data_jogo,
                url_bet=evento.get("event_url", ""),
                bookmaker=evento.get("bookmaker", "")
            )
            
        except Exception as e:
            print(f"Erro ao salvar histórico: {e}")
    
    def get_user_history(self, chat_id: int, limit: int = 100) -> List[Dict]:
        """Retorna histórico de um usuário"""
        return self.db.get_user_history(chat_id, limit)
    
    def get_user_stats(self, chat_id: int) -> Dict:
        """Retorna estatísticas de um usuário"""
        return self.db.get_user_stats(chat_id)
    
    def get_system_stats(self) -> Dict:
        """Retorna estatísticas do sistema"""
        return self.db.get_system_stats()

# Singleton global
_history_instance = None

def get_history() -> AlertHistory:
    """Retorna instância singleton do histórico"""
    global _history_instance
    if _history_instance is None:
        _history_instance = AlertHistory()
    return _history_instance
