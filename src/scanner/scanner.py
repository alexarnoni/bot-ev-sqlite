"""
Scanner principal - executa o scan de apostas
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from src.api.api_client import OddsAPI
from src.scanner.scan_cache import get_snapshot_cache
from src.core.database import SQLiteConnectionPool, SQLiteConnectionConfig
from src.filters.filtros import evento_valido, aplicar_filtros_dinamicos, validar_filtros_usuario
from src.api.rate_limiter import api_rate_limiter
from src.api.rate_limiter_global import get_global_rate_limiter
from src.api.status import get_odds_api_status
from src.utils.utils import carregar_catalogo_ligas
from src.bot.bot_ev import enviar_alertas_batch, enviar_alerta_instantaneo
from src.bot.bot_core import definir_stake
from src.data.cache import get_cache
from src.core.config import FEED_ID
from src.utils.messages import (
    api_offline, global_rate_limit, scan_rate_limit, 
    no_events, user_not_found, snapshot_expired, high_ev_alert
)
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
        
        # Calcula momento do scan uma vez para consistência
        momento_scan = datetime.now(timezone.utc)
        
        # Verifica status da API
        if not await get_odds_api_status():
            logger.warning("⚠️ API offline, pulando scan")
            return api_offline()
        
        # Verifica rate limit GLOBAL primeiro (sincrono)
        try:
            if not get_global_rate_limiter().can_make_request():
                logger.warning("⚠️ Rate limit global atingido, pulando scan")
                return global_rate_limit()
        except Exception:
            pass

        # Verifica rate limit local/por feed (async)
        if not await api_rate_limiter.can_make_request():
            logger.warning("⚠️ Rate limit atingido, pulando scan")
            return scan_rate_limit()
        
        # Busca usuários ativos
        usuarios_ativos = await _buscar_usuarios_ativos()
        if not usuarios_ativos:
            logger.info("📭 Nenhum usuário ativo encontrado")
            return "📭 Nenhum usuário ativo"
        
        # Busca apostas da API com base nos bookmakers dos usuários
        apostas = await _buscar_apostas_api(usuarios_ativos)
        if not apostas:
            logger.info("📭 Nenhuma aposta encontrada na API")
            return no_events()
        
        # Processa apostas para cada usuário com momento de scan consistente
        total_alertas = 0
        for usuario in usuarios_ativos:
            alertas_usuario = await _processar_apostas_usuario(usuario, apostas, momento_scan)
            total_alertas += len(alertas_usuario)
        
        logger.info(f"✅ Scan concluído: {total_alertas} alertas enviados")
        return f"📊 {total_alertas} alertas enviados"
        
    except Exception as e:
        logger.error(f"❌ Erro no scan: {e}")
        return f"❌ Erro: {e}"

async def scan_apostas_usuario(chat_id: str):
    """
    Scan individual para um usuário específico
    Usado pelo comando /scan manual
    """
    try:
        logger.info(f"🔍 Iniciando scan individual para usuário {chat_id}...")
        
        # Calcula momento do scan uma vez para consistência
        momento_scan = datetime.now(timezone.utc)
        
        # Busca dados do usuário específico
        usuario = await _buscar_usuario_especifico(chat_id)
        if not usuario:
            logger.info(f"📭 Usuário {chat_id} não encontrado ou inativo")
            return user_not_found()

        # Tenta usar snapshot recente do scan global
        snapshot_cache = get_snapshot_cache()
        required_bookmakers = usuario.get('bookmakers') or []
        snapshot = snapshot_cache.get_snapshot(max_age_seconds=120, required_bookmakers=required_bookmakers)

        if snapshot is not None:
            apostas = snapshot.get('eventos') or []
            logger.info("🧠 /scan usando snapshot global recente (sem chamada à API)")
        else:
            # Verificações SÓ quando precisa chamar a API
            # Verifica status da API
            if not await get_odds_api_status():
                logger.warning("⚠️ API offline, pulando scan")
                return api_offline()
            
            # Verifica rate limit GLOBAL primeiro
            try:
                if not get_global_rate_limiter().can_make_request():
                    logger.warning("⚠️ Rate limit global atingido, pulando scan")
                    return global_rate_limit()
            except Exception:
                pass

            # Verifica rate limit local/por feed
            if not await api_rate_limiter.can_make_request():
                logger.warning("⚠️ Rate limit atingido, pulando scan")
                return scan_rate_limit()
            
            # Busca apostas da API com base nos bookmakers do usuário
            apostas = await _buscar_apostas_api([usuario])
            
        if not apostas:
            logger.info("📭 Nenhuma aposta encontrada na API")
            return no_events()
        
        # Processa apostas para o usuário específico
        alertas_usuario = await _processar_apostas_usuario(usuario, apostas, momento_scan)
        
        logger.info(f"✅ Scan individual concluído para {chat_id}: {len(alertas_usuario)} alertas enviados")
        return f"📊 {len(alertas_usuario)} alertas enviados"
        
    except Exception as e:
        logger.error(f"❌ Erro no scan individual para {chat_id}: {e}")
        return f"❌ Erro: {e}"

async def _buscar_usuarios_ativos() -> List[Dict[str, Any]]:
    """
    Busca usuários ativos com suas configurações
    Otimizado: 1 query com JOINs em vez de N+1 queries
    """
    try:
        async with db_pool.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT 
                    u.chat_id,
                    u.nome,
                    uf.ev_faixa_min,
                    uf.ev_faixa_max,
                    uf.horario_inicio,
                    uf.horario_fim,
                    uf.data_inicio,
                    uf.data_fim,
                    uf.filtro_dias,
                    GROUP_CONCAT(DISTINCT ul.league) as ligas,
                    GROUP_CONCAT(DISTINCT us.sport) as esportes,
                    GROUP_CONCAT(DISTINCT ub.bookmaker) as bookmakers
                FROM users u
                LEFT JOIN user_filters uf ON u.chat_id = uf.chat_id
                LEFT JOIN user_leagues ul ON u.chat_id = ul.chat_id
                LEFT JOIN user_sports us ON u.chat_id = us.chat_id
                LEFT JOIN user_bookmakers ub ON u.chat_id = ub.chat_id
                WHERE u.is_active = 1 AND (u.is_blocked IS NULL OR u.is_blocked = 0)
                GROUP BY u.chat_id, u.nome, uf.ev_faixa_min, uf.ev_faixa_max, 
                         uf.horario_inicio, uf.horario_fim, uf.data_inicio, 
                         uf.data_fim, uf.filtro_dias
            """)
            
            usuarios = []
            for row in await cursor.fetchall():
                # Converte GROUP_CONCAT strings para listas
                ligas = row['ligas'].split(',') if row['ligas'] else []
                esportes = row['esportes'].split(',') if row['esportes'] else []
                bookmakers = row['bookmakers'].split(',') if row['bookmakers'] else []
                
                usuario = {
                    'chat_id': row['chat_id'],
                    'nome': row['nome'],
                    'filtros': {
                        'ev_faixa_min': row['ev_faixa_min'] or 0.05,
                        'ev_faixa_max': row['ev_faixa_max'] or 1.0,
                        'horario_inicio': row['horario_inicio'],
                        'horario_fim': row['horario_fim'],
                        'data_inicio': row['data_inicio'],
                        'data_fim': row['data_fim'],
                        'filtro_dias': row['filtro_dias']
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

async def _buscar_usuario_especifico(chat_id: str) -> Dict[str, Any]:
    """
    Busca um usuário específico com suas configurações
    Otimizado: 1 query com JOINs em vez de 4 queries
    """
    try:
        async with db_pool.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT 
                    u.chat_id,
                    u.nome,
                    uf.ev_faixa_min,
                    uf.ev_faixa_max,
                    uf.horario_inicio,
                    uf.horario_fim,
                    uf.data_inicio,
                    uf.data_fim,
                    uf.filtro_dias,
                    GROUP_CONCAT(DISTINCT ul.league) as ligas,
                    GROUP_CONCAT(DISTINCT us.sport) as esportes,
                    GROUP_CONCAT(DISTINCT ub.bookmaker) as bookmakers
                FROM users u
                LEFT JOIN user_filters uf ON u.chat_id = uf.chat_id
                LEFT JOIN user_leagues ul ON u.chat_id = ul.chat_id
                LEFT JOIN user_sports us ON u.chat_id = us.chat_id
                LEFT JOIN user_bookmakers ub ON u.chat_id = ub.chat_id
                WHERE u.chat_id = ? AND u.is_active = 1 AND (u.is_blocked IS NULL OR u.is_blocked = 0)
                GROUP BY u.chat_id, u.nome, uf.ev_faixa_min, uf.ev_faixa_max, 
                         uf.horario_inicio, uf.horario_fim, uf.data_inicio, 
                         uf.data_fim, uf.filtro_dias
            """, (chat_id,))
            
            row = await cursor.fetchone()
            if not row:
                return None
            
            # Converte GROUP_CONCAT strings para listas
            ligas = row['ligas'].split(',') if row['ligas'] else []
            esportes = row['esportes'].split(',') if row['esportes'] else []
            bookmakers = row['bookmakers'].split(',') if row['bookmakers'] else []
            
            usuario = {
                'chat_id': row['chat_id'],
                'nome': row['nome'],
                'filtros': {
                    'ev_faixa_min': row['ev_faixa_min'],
                    'ev_faixa_max': row['ev_faixa_max'],
                    'horario_inicio': row['horario_inicio'],
                    'horario_fim': row['horario_fim'],
                    'data_inicio': row['data_inicio'],
                    'data_fim': row['data_fim'],
                    'filtro_dias': row['filtro_dias']
                },
                'ligas': ligas,
                'esportes': esportes,
                'bookmakers': bookmakers
            }
            
            return usuario
        
    except Exception as e:
        logger.error(f"Erro ao buscar usuário específico {chat_id}: {e}")
        return None

async def _buscar_apostas_api(usuarios_ativos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Busca apostas da API Odds
    """
    try:
        # Cria cliente da API
        api_client = OddsAPI()

        # 1) Coletar bookmakers únicos dos usuários
        bookmakers_unicos = set()
        for user in usuarios_ativos or []:
            user_bks = user.get('bookmakers') or []
            if isinstance(user_bks, str):
                user_bks = [b.strip() for b in user_bks.split(',') if b.strip()]
            for bk in user_bks:
                if bk and bk != 'Stake.bet.br':  # remove casa inexistente
                    bookmakers_unicos.add(bk)

        if not bookmakers_unicos:
            logger.info("Nenhum bookmaker configurado pelos usuários")
            return []

        # 2) Buscar apostas por bookmaker individualmente
        todos_eventos: List[Dict[str, Any]] = []
        for bk in bookmakers_unicos:
            try:
                eventos_bk = await api_client.get_eventos_geral(bk)
                todos_eventos.extend(eventos_bk)
                logger.info(f"📊 {bk}: {len(eventos_bk)} eventos")
            except Exception as e:
                logger.error(f"Erro ao buscar {bk}: {e}")

        return todos_eventos
        
    except Exception as e:
        logger.error(f"Erro ao buscar apostas da API: {e}")
        return []

async def _processar_apostas_usuario(usuario: Dict[str, Any], apostas: List[Dict[str, Any]], momento_scan: datetime = None) -> List[Dict[str, Any]]:
    """
    Processa apostas para um usuário específico - PADRONIZADO COM SCAN AUTOMÁTICO
    """
    try:
        chat_id = usuario['chat_id']
        filtros = usuario['filtros']
        
        # Calcula janela de tempo dinâmica uma vez por usuário
        janela_tempo = None
        filtro_dias = filtros.get("filtro_dias")
        if filtro_dias and momento_scan:
            from src.filters.filtros import calcular_janela_tempo_dinamica
            janela_tempo = calcular_janela_tempo_dinamica(filtro_dias, momento_scan)
        
        # Filtra eventos válidos (MESMA LÓGICA DO SCAN AUTOMÁTICO)
        eventos_validos = []
        for aposta in apostas:
            # Ignora eventos com liga desconhecida
            league_name = (aposta.get('league') or '').strip()
            if not league_name or league_name.lower() == 'unknown':
                continue
            
            # Ignora eventos já iniciados
            try:
                commence_iso = aposta.get('commence_time')
                if commence_iso:
                    jogo_time = datetime.fromisoformat(commence_iso.replace('Z', '+00:00'))
                    if jogo_time.tzinfo is None:
                        jogo_time = jogo_time.replace(tzinfo=timezone.utc)
                    agora = momento_scan if momento_scan else datetime.now(timezone.utc)
                    if jogo_time <= agora:
                        continue
            except Exception:
                pass
            
            # Aplica filtros do usuário incluindo bookmakers (MESMA LÓGICA)
            if not evento_valido(aposta, filtros):
                continue
            
            # Verifica filtros específicos do usuário (bookmakers, ligas, esportes)
            ligas_usuario = usuario.get('ligas', [])
            esportes_usuario = usuario.get('esportes', [])
            bookmakers_usuario = usuario.get('bookmakers', [])
            
            if not validar_filtros_usuario(aposta, filtros, ligas_usuario, esportes_usuario, bookmakers_usuario):
                continue
            
            # Aplica filtros dinâmicos (MESMA LÓGICA)
            if not aplicar_filtros_dinamicos(aposta, filtros, janela_tempo):
                continue
            
            eventos_validos.append(aposta)
        
        if not eventos_validos:
            return []
        
        # Remove duplicatas do cache (MESMA LÓGICA)
        cache = get_cache()
        eventos_novos = []
        for evento in eventos_validos:
            if not cache.is_duplicate(chat_id, evento):
                eventos_novos.append(evento)
        
        if not eventos_novos:
            return []
        
        # Calcula stake e separa alertas por prioridade
        alertas_normais = []
        alertas_instantaneos = []
        
        for evento in eventos_novos:
            ev = evento.get('ev', 0)
            stake = definir_stake(ev, evento.get('bet365_odds', 0))
            
            if stake > 0:
                # EV+ 10% = instantâneo
                if ev >= 0.10:  # 10% em decimal
                    alertas_instantaneos.append((evento, stake))
                    logger.info(high_ev_alert(ev))
                else:
                    alertas_normais.append((evento, stake))
        
        # Envia alertas instantâneos IMEDIATAMENTE
        alertas_enviados = 0
        for evento, stake in alertas_instantaneos:
            try:
                await enviar_alerta_instantaneo(chat_id, evento, stake)
                alertas_enviados += 1
                
                # Adiciona ao cache e histórico
                cache.add_alert(chat_id, evento)
                await _salvar_no_historico(chat_id, evento)
                
            except Exception as e:
                logger.error(f"Erro ao enviar alerta instantâneo para {chat_id}: {e}")
        
        # Envia alertas normais em batches
        if alertas_normais:
            for i in range(0, len(alertas_normais), 5):  # Batch de 5
                batch = alertas_normais[i:i+5]
                try:
                    await enviar_alertas_batch(chat_id, batch)
                    alertas_enviados += len(batch)
                    
                    # Adiciona ao cache e histórico
                    for evento, stake in batch:
                        cache.add_alert(chat_id, evento)
                        await _salvar_no_historico(chat_id, evento)
                        
                except Exception as e:
                    logger.error(f"Erro ao enviar batch para {chat_id}: {e}")
        
        return [evento for evento, stake in alertas_instantaneos + alertas_normais]
        
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
        # Gera hash consistente com banco
        from src.core.database import generate_alert_hash
        alert_hash = generate_alert_hash(aposta)

        async with db_pool.get_connection() as conn:
            await conn.execute("""
                INSERT INTO alert_history 
                (chat_id, data_envio, alert_hash, esporte, home, away, mercado, odd, stake, ev, data_jogo, url_bet, bookmaker)
                VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chat_id,
                alert_hash,
                aposta.get('sport', ''),
                aposta.get('home', ''),
                aposta.get('away', ''),
                aposta.get('market_type', ''),
                aposta.get('bet365_odds', 0),
                aposta.get('stake', 0),
                aposta.get('ev', 0),
                aposta.get('commence_time', ''),
                aposta.get('event_url', ''),
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
