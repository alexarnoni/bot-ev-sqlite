"""
Scanner principal - executa o scan de apostas
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from api_client import OddsAPI
from database import SQLiteConnectionPool, SQLiteConnectionConfig
from filtros import validar_filtros
from rate_limiter import api_rate_limiter
from status import get_odds_api_status
from utils import carregar_catalogo_ligas
from bot_ev import enviar_alerta
from config import FEED_ID
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

logger = logging.getLogger(__name__)

async def scan_apostas():
    """
    Função principal de scan de apostas
    Executada a cada 2 minutos pelo scheduler
    """
    try:
        logger.info("🔍 Iniciando scan de apostas...")
        
        # Verifica status da API
        if not await get_odds_api_status():
            logger.warning("⚠️ API offline, pulando scan")
            return
        
        # Verifica rate limit
        if not await api_rate_limiter.can_make_request():
            logger.warning("⚠️ Rate limit atingido, pulando scan")
            return
        
        # Busca usuários ativos
        usuarios_ativos = await _buscar_usuarios_ativos()
        if not usuarios_ativos:
            logger.info("📭 Nenhum usuário ativo encontrado")
            return
        
        # Busca apostas da API
        apostas = await _buscar_apostas_api()
        if not apostas:
            logger.info("📭 Nenhuma aposta encontrada na API")
            return
        
        # Processa apostas para cada usuário
        total_alertas = 0
        for usuario in usuarios_ativos:
            alertas_usuario = await _processar_apostas_usuario(usuario, apostas)
            total_alertas += len(alertas_usuario)
        
        logger.info(f"✅ Scan concluído: {total_alertas} alertas enviados")
        
    except Exception as e:
        logger.error(f"❌ Erro no scan de apostas: {e}")

async def _buscar_usuarios_ativos() -> List[Dict[str, Any]]:
    """
    Busca usuários ativos com suas configurações
    """
    try:
        async with db_pool.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT 
                    u.chat_id,
                    u.nome,
                    uf.ev_minimo,
                    uf.ev_maximo,
                    uf.horario_inicio,
                    uf.horario_fim,
                    uf.data_inicio,
                    uf.data_fim
                FROM users u
                LEFT JOIN user_filters uf ON u.chat_id = uf.chat_id
                WHERE u.is_active = 1
            """)
            
            usuarios = []
            for row in await cursor.fetchall():
                # Busca ligas do usuário
                cursor_ligas = await conn.execute("""
                    SELECT league_name FROM user_leagues WHERE chat_id = ?
                """, (row['chat_id'],))
                ligas = [liga['league_name'] for liga in await cursor_ligas.fetchall()]
                
                # Busca esportes do usuário
                cursor_esportes = await conn.execute("""
                    SELECT sport_name FROM user_sports WHERE chat_id = ?
                """, (row['chat_id'],))
                esportes = [esporte['sport_name'] for esporte in await cursor_esportes.fetchall()]
                
                # Busca bookmakers do usuário
                cursor_bookmakers = await conn.execute("""
                    SELECT bookmaker_name FROM user_bookmakers WHERE chat_id = ?
                """, (row['chat_id'],))
                bookmakers = [bm['bookmaker_name'] for bm in await cursor_bookmakers.fetchall()]
                
                usuario = {
                    'chat_id': row['chat_id'],
                    'nome': row['nome'],
                    'filtros': {
                        'ev_minimo': row['ev_minimo'] or 0.05,
                        'ev_maximo': row['ev_maximo'] or 1.0,
                        'horario_inicio': row['horario_inicio'],
                        'horario_fim': row['horario_fim'],
                        'data_inicio': row['data_inicio'],
                        'data_fim': row['data_fim']
                    },
                    'ligas': ligas,
                    'esportes': esportes,
                    'bookmakers': bookmakers
                }
                usuarios.append(usuario)
            
            return usuarios
            
    except Exception as e:
        logger.error(f"Erro ao buscar usuários ativos: {e}")
        return []

async def _buscar_apostas_api() -> List[Dict[str, Any]]:
    """
    Busca apostas da API Odds
    """
    try:
        # Registra request no rate limiter
        await api_rate_limiter.log_request()
        
        # Cria cliente da API
        api_client = OddsAPI()
        
        # Busca apostas
        apostas = await api_client.get_apostas()
        
        return apostas or []
        
    except Exception as e:
        logger.error(f"Erro ao buscar apostas da API: {e}")
        return []

async def _processar_apostas_usuario(usuario: Dict[str, Any], apostas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Processa apostas para um usuário específico
    """
    try:
        alertas = []
        
        for aposta in apostas:
            # Aplica filtros do usuário
            if not validar_filtros(aposta, usuario['filtros'], usuario['ligas'], 
                                 usuario['esportes'], usuario['bookmakers']):
                continue
            
            # Verifica se já foi enviado (cache)
            if await _ja_foi_enviado(usuario['chat_id'], aposta):
                continue
            
            # Envia alerta
            await enviar_alerta(usuario['chat_id'], aposta)
            
            # Salva no cache
            await _salvar_no_cache(usuario['chat_id'], aposta)
            
            # Salva no histórico
            await _salvar_no_historico(usuario['chat_id'], aposta)
            
            alertas.append(aposta)
        
        return alertas
        
    except Exception as e:
        logger.error(f"Erro ao processar apostas para usuário {usuario['chat_id']}: {e}")
        return []

async def _ja_foi_enviado(chat_id: int, aposta: Dict[str, Any]) -> bool:
    """
    Verifica se o alerta já foi enviado (cache)
    """
    try:
        # Gera hash único da aposta
        hash_aposta = _gerar_hash_aposta(aposta)
        
        async with db_pool.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT COUNT(*) as count FROM alert_cache 
                WHERE chat_id = ? AND alert_hash = ?
            """, (chat_id, hash_aposta))
            
            return (await cursor.fetchone())['count'] > 0
            
    except Exception as e:
        logger.error(f"Erro ao verificar cache: {e}")
        return False

async def _salvar_no_cache(chat_id: int, aposta: Dict[str, Any]):
    """
    Salva alerta no cache para evitar duplicatas
    """
    try:
        hash_aposta = _gerar_hash_aposta(aposta)
        
        async with db_pool.get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO alert_cache 
                (chat_id, alert_hash, created_at)
                VALUES (?, ?, datetime('now'))
            """, (chat_id, hash_aposta))
            
    except Exception as e:
        logger.error(f"Erro ao salvar no cache: {e}")

async def _salvar_no_historico(chat_id: int, aposta: Dict[str, Any]):
    """
    Salva alerta no histórico
    """
    try:
        async with db_pool.get_connection() as conn:
            await conn.execute("""
                INSERT INTO alert_history 
                (chat_id, home, away, league, sport, market_type, bet_side, 
                 odds, ev, stake, bookmaker, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                chat_id,
                aposta.get('home', ''),
                aposta.get('away', ''),
                aposta.get('league', ''),
                aposta.get('sport', ''),
                aposta.get('market_type', ''),
                aposta.get('bet_side', ''),
                aposta.get('bet365_odds', 0),
                aposta.get('ev', 0),
                aposta.get('stake', 0),
                aposta.get('bookmaker', ''),
            ))
            
    except Exception as e:
        logger.error(f"Erro ao salvar no histórico: {e}")

def _gerar_hash_aposta(aposta: Dict[str, Any]) -> str:
    """
    Gera hash único para a aposta
    """
    import hashlib
    
    # Cria string única baseada nos dados da aposta
    dados = f"{aposta.get('home', '')}_{aposta.get('away', '')}_{aposta.get('league', '')}_{aposta.get('market_type', '')}_{aposta.get('bet_side', '')}_{aposta.get('bet365_odds', 0)}"
    
    # Gera hash MD5
    return hashlib.md5(dados.encode()).hexdigest()
