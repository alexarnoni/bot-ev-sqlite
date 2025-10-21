"""
Scanner principal - executa o scan de apostas
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from api_client import OddsAPI
from database import SQLiteConnectionPool, SQLiteConnectionConfig
from filtros import evento_valido, aplicar_filtros_dinamicos, validar_filtros_usuario, validar_filtros_americanos
from rate_limiter import api_rate_limiter
from status import get_odds_api_status
from utils import carregar_catalogo_ligas
from bot_ev import enviar_alertas_batch, enviar_alerta_instantaneo
from bot_core import definir_stake
from cache import get_cache
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
        
        # Calcula momento do scan uma vez para consistência
        momento_scan = datetime.now(timezone.utc)
        
        # Verifica status da API
        if not await get_odds_api_status():
            logger.warning("⚠️ API offline, pulando scan")
            return "⚠️ API offline"
        
        # Verifica rate limit
        if not await api_rate_limiter.can_make_request():
            logger.warning("⚠️ Rate limit atingido, pulando scan")
            return "⚠️ Rate limit atingido"
        
        # Busca usuários ativos
        usuarios_ativos = await _buscar_usuarios_ativos()
        if not usuarios_ativos:
            logger.info("📭 Nenhum usuário ativo encontrado")
            return "📭 Nenhum usuário ativo"
        
        # Busca apostas da API com base nos bookmakers dos usuários
        apostas = await _buscar_apostas_api(usuarios_ativos)
        if not apostas:
            logger.info("📭 Nenhuma aposta encontrada na API")
            return "📭 Nenhuma aposta encontrada"
        
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
        
        # Verifica status da API
        if not await get_odds_api_status():
            logger.warning("⚠️ API offline, pulando scan")
            return "⚠️ API offline"
        
        # Verifica rate limit
        if not await api_rate_limiter.can_make_request():
            logger.warning("⚠️ Rate limit atingido, pulando scan")
            return "⚠️ Rate limit atingido"
        
        # Busca dados do usuário específico
        usuario = await _buscar_usuario_especifico(chat_id)
        if not usuario:
            logger.info(f"📭 Usuário {chat_id} não encontrado ou inativo")
            return "📭 Usuário não encontrado ou inativo"
        
        # Busca apostas da API com base nos bookmakers do usuário
        apostas = await _buscar_apostas_api([usuario])
        if not apostas:
            logger.info("📭 Nenhuma aposta encontrada na API")
            return "📭 Nenhuma aposta encontrada"
        
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

def processar_props_com_ev(props: List[Dict], ev_min: float) -> List[Dict]:
    """
    Processa player props e filtra por EV mínimo
    
    Args:
        props: Lista de props retornados pela API
        ev_min: EV mínimo configurado pelo usuário
        
    Returns:
        Lista de props com EV+ acima do mínimo, incluindo melhor bookmaker
    """
    from bot_core import calcular_ev_player_prop
    
    props_validos = []
    
    for prop in props:
        try:
            # Calcular EV para todas as casas
            ev_data = calcular_ev_player_prop(prop)
            
            if not ev_data:
                continue
            
            # Encontrar melhor casa (maior EV positivo)
            melhor_casa = max(ev_data.items(), key=lambda x: x[1]['best_ev'])
            bookmaker_name = melhor_casa[0]
            ev_info = melhor_casa[1]
            
            # Filtrar por EV mínimo
            if ev_info['best_ev'] >= ev_min:
                # Adicionar informações do melhor bookmaker ao prop
                prop['ev'] = ev_info['best_ev']
                prop['bookmaker'] = bookmaker_name
                prop['bet_side'] = ev_info['best']  # 'over' ou 'under'
                prop['odds'] = ev_info['best_odds']
                prop['bet365_odds'] = ev_info['best_odds']  # Para compatibilidade com formatador
                prop['is_player_prop'] = True
                
                # Formatar nome para exibição
                prop_type_display = prop['prop_type'].replace('_', ' ').title()
                side_display = 'Over' if ev_info['best'] == 'over' else 'Under'
                prop['bet_side'] = f"{prop['player_name']} - {prop_type_display} {side_display} {prop['line']}"
                
                props_validos.append(prop)
        
        except Exception as e:
            logger.error(f"Erro ao processar prop: {e}")
            continue
    
    return props_validos

def limitar_props_por_jogo(props: List[Dict], max_per_game: int = 5) -> List[Dict]:
    """
    Limita o número de props por jogo aos com maior EV
    
    Args:
        props: Lista de props com EV calculado
        max_per_game: Número máximo de props por jogo
        
    Returns:
        Lista filtrada com no máximo max_per_game props por evento
    """
    # Agrupar por event_id
    por_jogo = {}
    for prop in props:
        eid = prop.get('event_id')
        if eid not in por_jogo:
            por_jogo[eid] = []
        por_jogo[eid].append(prop)
    
    # Pegar top N por jogo (maior EV)
    resultado = []
    for eid, props_jogo in por_jogo.items():
        # Ordenar por EV (maior primeiro)
        top = sorted(props_jogo, key=lambda x: x.get('ev', 0), reverse=True)[:max_per_game]
        resultado.extend(top)
        
        if len(props_jogo) > max_per_game:
            logger.info(f"Limitado props do evento {eid}: {len(props_jogo)} -> {max_per_game}")
    
    return resultado

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
            from filtros import calcular_janela_tempo_dinamica
            janela_tempo = calcular_janela_tempo_dinamica(filtro_dias, momento_scan)
        
        # Filtra eventos válidos (MESMA LÓGICA DO SCAN AUTOMÁTICO)
        eventos_validos = []
        total_processados = 0
        rejeitados_liga = 0
        rejeitados_data = 0
        rejeitados_evento_valido = 0
        rejeitados_filtros_usuario = 0
        rejeitados_americanos = 0
        rejeitados_dinamicos = 0
        
        for aposta in apostas:
            total_processados += 1
            
            # Ignora eventos com liga desconhecida
            league_name = (aposta.get('league') or '').strip()
            if not league_name or league_name.lower() == 'unknown':
                rejeitados_liga += 1
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
                        rejeitados_data += 1
                        continue
            except Exception:
                pass
            
            # 🔍 LOG: Evento chegou até aqui
            if total_processados <= 3:  # Log apenas primeiros 3 para não poluir
                logger.info(f"🔍 Evento #{total_processados}: Sport={aposta.get('sport')} | Liga={league_name} | EV={aposta.get('ev', 0):.2%} | Bookmaker={aposta.get('bookmaker')}")
            
            # Aplica filtros do usuário incluindo bookmakers (MESMA LÓGICA)
            if not evento_valido(aposta, filtros):
                rejeitados_evento_valido += 1
                if total_processados <= 3:
                    logger.info(f"❌ #{total_processados} Rejeitado em evento_valido()")
                continue
            
            # Verifica filtros específicos do usuário (bookmakers, ligas, esportes)
            ligas_usuario = usuario.get('ligas', [])
            esportes_usuario = usuario.get('esportes', [])
            bookmakers_usuario = usuario.get('bookmakers', [])
            
            if not validar_filtros_usuario(aposta, filtros, ligas_usuario, esportes_usuario, bookmakers_usuario):
                rejeitados_filtros_usuario += 1
                if total_processados <= 3:
                    logger.info(f"❌ #{total_processados} Rejeitado em validar_filtros_usuario()")
                continue
            
            # Aplica filtros específicos do feed americano
            if not validar_filtros_americanos(aposta, filtros, FEED_ID):
                rejeitados_americanos += 1
                if total_processados <= 3:
                    logger.info(f"❌ #{total_processados} Rejeitado em validar_filtros_americanos()")
                continue
            
            # Aplica filtros dinâmicos (MESMA LÓGICA)
            if not aplicar_filtros_dinamicos(aposta, filtros, janela_tempo):
                rejeitados_dinamicos += 1
                if total_processados <= 3:
                    logger.info(f"❌ #{total_processados} Rejeitado em aplicar_filtros_dinamicos()")
                continue
            
            eventos_validos.append(aposta)
        
        # 📊 RESUMO DO SCAN
        logger.info(f"📊 RESUMO DO SCAN para usuário {chat_id}:")
        logger.info(f"   Total de eventos da API: {total_processados}")
        logger.info(f"   ❌ Rejeitados (liga unknown): {rejeitados_liga}")
        logger.info(f"   ❌ Rejeitados (data/horário): {rejeitados_data}")
        logger.info(f"   ❌ Rejeitados (evento_valido): {rejeitados_evento_valido}")
        logger.info(f"   ❌ Rejeitados (filtros_usuario): {rejeitados_filtros_usuario}")
        logger.info(f"   ❌ Rejeitados (filtros_americanos): {rejeitados_americanos}")
        logger.info(f"   ❌ Rejeitados (filtros_dinamicos): {rejeitados_dinamicos}")
        logger.info(f"   ✅ Eventos aceitos: {len(eventos_validos)}")
        
        # 🎯 BUSCAR PLAYER PROPS (se habilitado)
        include_props = filtros.get('include_props', False)
        
        # Para feed americano, props sempre ativados
        if FEED_ID == 'feed_american':
            include_props = True
        
        if include_props:
            try:
                logger.info("🎯 Buscando player props...")
                
                # Extrair event_ids de eventos americanos com EV+
                eventos_com_ev = [e for e in eventos_validos if e.get('ev', 0) > 0.01]
                event_ids = list(set([e.get('event_id') for e in eventos_com_ev if e.get('event_id')]))
                
                # Fallback: se não houver EV+, buscar próximos jogos americanos
                if not event_ids and FEED_ID == 'feed_american':
                    logger.info("⚠️ Nenhum evento com EV+, buscando próximos jogos americanos...")
                    api_client = OddsAPI()
                    event_ids = await api_client.get_upcoming_american_events(limit=5)
                
                if event_ids:
                    logger.info(f"📍 Buscando props para {len(event_ids)} eventos")
                    
                    # Buscar props
                    api_client = OddsAPI()
                    props = await api_client.get_player_props_batch(event_ids, bookmakers_usuario)
                    
                    if props:
                        # Processar props com EV
                        props_com_ev = processar_props_com_ev(props, filtros.get('ev_faixa_min', 0.01))
                        
                        # Limitar a top 5 por jogo
                        if props_com_ev:
                            props_filtrados = limitar_props_por_jogo(props_com_ev, max_per_game=5)
                            
                            if props_filtrados:
                                logger.info(f"✅ {len(props_filtrados)} player props encontrados com EV+")
                                eventos_validos.extend(props_filtrados)
                            else:
                                logger.info("⚠️ Nenhum prop passou no filtro de EV mínimo")
                        else:
                            logger.info("⚠️ Nenhum prop com EV+ encontrado")
                    else:
                        logger.info("⚠️ Nenhum prop retornado pela API")
                else:
                    logger.info("⚠️ Nenhum event_id disponível para buscar props")
            
            except Exception as e:
                logger.error(f"❌ Erro ao buscar player props: {e}")
                import traceback
                traceback.print_exc()
        
        if not eventos_validos:
            return []
        
        # Remove duplicatas do cache (MESMA LÓGICA)
        cache = get_cache()
        eventos_novos = []
        duplicatas = 0
        for evento in eventos_validos:
            if not cache.is_duplicate(chat_id, evento):
                eventos_novos.append(evento)
            else:
                duplicatas += 1
        
        logger.info(f"🔄 Cache: {duplicatas} duplicatas removidas, {len(eventos_novos)} eventos novos")
        
        if not eventos_novos:
            logger.info(f"⚠️ Todos os {len(eventos_validos)} eventos já foram enviados anteriormente (cache)")
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
                    logger.info(f"🚨 Alerta de alta prioridade detectado para {chat_id}: EV {ev:.2%}")
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
        async with db_pool.get_connection() as conn:
            await conn.execute("""
                INSERT INTO alert_history 
                (chat_id, data_envio, esporte, home, away, mercado, odd, stake, ev, data_jogo, url_bet, bookmaker)
                VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chat_id,
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

