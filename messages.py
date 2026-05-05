"""
Mensagens padronizadas para UX consistente
"""
from typing import Optional

class StandardMessages:
    """Centralized message templates for consistent UX"""
    
    # API Status Messages
    API_OFFLINE = "⚠️ Sistema temporariamente indisponível. Tente novamente em alguns minutos."
    API_RATE_LIMIT = "⏱️ Limite de requisições atingido. Aguarde {minutes} minutos."
    API_ERROR = "❌ Erro temporário na API. Tente novamente."
    
    # Scan Messages
    SCAN_SNAPSHOT_EXPIRED = "🔄 Dados atualizados. Executando nova busca..."
    SCAN_NO_EVENTS = "📭 Nenhuma oportunidade encontrada no momento."
    SCAN_RATE_LIMIT = "⏱️ Limite de scan atingido. Aguarde antes de tentar novamente."
    SCAN_GLOBAL_RATE_LIMIT = "⏱️ Sistema ocupado. Tente novamente em alguns minutos."
    
    # User Configuration Messages
    USER_NOT_CONFIGURED = "⚙️ Configure seus filtros primeiro com /config"
    USER_NOT_FOUND = "👤 Usuário não encontrado ou inativo"
    USER_BLOCKED = "🚫 Usuário bloqueado administrativamente"
    
    # Alert Messages
    ALERT_INSTANT_HIGH_EV = "🚨 Alerta de alta prioridade detectado: EV {ev:.1%}"
    ALERT_SENT_SUCCESS = "✅ {count} alerta(s) enviado(s)"
    ALERT_SEND_ERROR = "❌ Erro ao enviar alerta"
    
    # Database Messages
    DB_ERROR = "❌ Erro temporário no banco de dados"
    DB_CONNECTION_ERROR = "🔌 Erro de conexão com o banco"
    
    # System Messages
    SYSTEM_STARTING = "🚀 Sistema iniciando..."
    SYSTEM_STOPPING = "🛑 Sistema parando..."
    SYSTEM_ERROR = "❌ Erro interno do sistema"
    
    # Validation Messages
    INVALID_BOOKMAKER = "📚 Bookmaker '{bookmaker}' não suportado"
    INVALID_LEAGUE = "🏆 Liga '{league}' não encontrada"
    INVALID_SPORT = "⚽ Esporte '{sport}' não suportado"
    
    # Success Messages
    CONFIG_UPDATED = "✅ Configuração atualizada com sucesso"
    FILTERS_APPLIED = "🔍 Filtros aplicados com sucesso"
    CACHE_CLEARED = "🧹 Cache limpo com sucesso"
    
    @staticmethod
    def format_message(template: str, **kwargs) -> str:
        """Format a message template with provided values"""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"{template} [Erro de formatação: {e}]"
    
    @staticmethod
    def get_rate_limit_message(minutes: int = 5) -> str:
        """Get rate limit message with default wait time"""
        return StandardMessages.format_message(
            StandardMessages.API_RATE_LIMIT, 
            minutes=minutes
        )
    
    @staticmethod
    def get_scan_rate_limit_message() -> str:
        """Get scan rate limit message"""
        return StandardMessages.SCAN_RATE_LIMIT
    
    @staticmethod
    def get_high_ev_alert_message(ev: float) -> str:
        """Get high EV alert message"""
        return StandardMessages.format_message(
            StandardMessages.ALERT_INSTANT_HIGH_EV,
            ev=ev
        )
    
    @staticmethod
    def get_invalid_bookmaker_message(bookmaker: str) -> str:
        """Get invalid bookmaker message"""
        return StandardMessages.format_message(
            StandardMessages.INVALID_BOOKMAKER,
            bookmaker=bookmaker
        )
    
    @staticmethod
    def get_invalid_league_message(league: str) -> str:
        """Get invalid league message"""
        return StandardMessages.format_message(
            StandardMessages.INVALID_LEAGUE,
            league=league
        )
    
    @staticmethod
    def get_invalid_sport_message(sport: str) -> str:
        """Get invalid sport message"""
        return StandardMessages.format_message(
            StandardMessages.INVALID_SPORT,
            sport=sport
        )

# Convenience functions for common messages
def api_offline() -> str:
    return StandardMessages.API_OFFLINE

def rate_limit(minutes: int = 5) -> str:
    return StandardMessages.get_rate_limit_message(minutes)

def scan_rate_limit() -> str:
    return StandardMessages.SCAN_RATE_LIMIT

def global_rate_limit() -> str:
    return StandardMessages.SCAN_GLOBAL_RATE_LIMIT

def no_events() -> str:
    return StandardMessages.SCAN_NO_EVENTS

def snapshot_expired() -> str:
    return StandardMessages.SCAN_SNAPSHOT_EXPIRED

def user_not_configured() -> str:
    return StandardMessages.USER_NOT_CONFIGURED

def user_not_found() -> str:
    return StandardMessages.USER_NOT_FOUND

def user_blocked() -> str:
    return StandardMessages.USER_BLOCKED

def high_ev_alert(ev: float) -> str:
    return StandardMessages.get_high_ev_alert_message(ev)

def alerts_sent(count: int) -> str:
    return StandardMessages.format_message(
        StandardMessages.ALERT_SENT_SUCCESS,
        count=count
    )

def config_updated() -> str:
    return StandardMessages.CONFIG_UPDATED

def invalid_bookmaker(bookmaker: str) -> str:
    return StandardMessages.get_invalid_bookmaker_message(bookmaker)

def invalid_league(league: str) -> str:
    return StandardMessages.get_invalid_league_message(league)

def invalid_sport(sport: str) -> str:
    return StandardMessages.get_invalid_sport_message(sport)
