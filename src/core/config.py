"""
Configuração do Bot EV+ com suporte a múltiplos feeds
"""
import os
from typing import List
from dotenv import load_dotenv

# Carrega variáveis de ambiente (override=False preserva vars já definidas, ex: FEED_ID via systemd)
load_dotenv(override=False)

# Configuração de feeds
FEEDS = os.getenv("FEEDS", "feed1").split()
FEED_ID = os.getenv("FEED_ID", "feed1")

# Tokens por feed (configurar via env vars)
FEED_TOKENS = {
    "default": os.getenv("BOT_TOKEN_DEFAULT"),
    "feed1": os.getenv("BOT_TOKEN_FEED1"),
    "feed2": os.getenv("BOT_TOKEN_FEED2"),
    "feed3": os.getenv("BOT_TOKEN_FEED3"),
    "feed4": os.getenv("BOT_TOKEN_FEED4"),
    "feed5": os.getenv("BOT_TOKEN_FEED5"),
    "feed_test": os.getenv("BOT_TOKEN_FEED_TEST"),
}

# API Odds
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
ODDS_API_BASE = "https://api.odds-api.io/v3"

# Paths base
# Navigate up from src/core/ to project root: __file__ → src/core/ → src/ → project_root/
BASE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOT_DATA_ROOT = os.getenv("BOT_DATA_ROOT", "data")

def feed_path(filename: str, feed_id: str = None) -> str:
    """Retorna o path completo para um arquivo específico do feed"""
    if feed_id is None:
        feed_id = FEED_ID
    
    feed_dir = os.path.join(BASE_PATH, BOT_DATA_ROOT, feed_id)
    os.makedirs(feed_dir, exist_ok=True)
    return os.path.join(feed_dir, filename)

def get_filters_path(feed_id: str = None) -> str:
    """Path para arquivo de filtros (legado JSON)"""
    return feed_path("filtros_por_chat.json", feed_id)

def get_cache_dir(feed_id: str = None) -> str:
    """Diretório de cache (legado Pickle)"""
    cache_dir = feed_path("cache", feed_id)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def get_historico_dir(feed_id: str = None) -> str:
    """Diretório de histórico (legado CSV)"""
    hist_dir = feed_path("historico_apostas", feed_id)
    os.makedirs(hist_dir, exist_ok=True)
    return hist_dir

def get_pendentes_dir(feed_id: str = None) -> str:
    """Diretório de alertas pendentes (legado JSON)"""
    pend_dir = feed_path("pendentes", feed_id)
    os.makedirs(pend_dir, exist_ok=True)
    return pend_dir

def get_bot_token(feed_id: str = None) -> str:
    """Retorna o token do bot para o feed especificado"""
    if feed_id is None:
        feed_id = FEED_ID
    return FEED_TOKENS.get(feed_id)

def get_telegram_token() -> str:
    """Retorna o token do Telegram para o feed atual"""
    current_feed = os.getenv("FEED_ID", FEED_ID)
    return get_bot_token(current_feed)

def get_listener_log_path() -> str:
    """Retorna o path do log do listener"""
    log_dir = os.path.join(BASE_PATH, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, f"listener_{FEED_ID}.log")

def get_database_path(feed_id: str = None) -> str:
    """Retorna o caminho unificado do banco do feed atual (bot.db)."""
    return feed_path("bot.db", feed_id)

# Configurações do sistema
RATE_LIMIT_REQUESTS_PER_HOUR = 90  # Buffer de segurança
THRESHOLD_EV_ALTO = 0.08  # 8% — alertas com EV >= este valor recebem template destacado
MAX_CONCURRENT_SCANS = 3
CACHE_CLEANUP_DAYS = 30
REQUEST_LOG_CLEANUP_HOURS = 2

# Admin users (configurar via env var)
ADMIN_USERS = [int(x) for x in os.getenv("ADMIN_USERS", "").split(",") if x.strip()]

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
