"""
Sistema de filtros para validação de eventos
"""
from datetime import datetime, time, timezone, timedelta
from typing import Dict, Any

# Mercados proibidos (Half Time)
MERCADOS_PROIBIDOS = [
    'half time', 'ht', '1st half', 'primeiro tempo',
    'segundo tempo', '2nd half', '2h', '2º tempo'
]

def odd_valida(odd: float) -> bool:
    """Verifica se a odd é válida para apostas"""
    try:
        odd_float = float(odd)
        return 1.50 <= odd_float <= 50.0
    except (TypeError, ValueError):
        return False

def esta_dentro_do_ev(ev: float, ev_min: float = None, ev_max: float = None) -> bool:
    """Verifica se EV está dentro da faixa configurada"""
    try:
        ev_float = float(ev)
        
        if ev_min is not None and ev_float < float(ev_min):
            return False
        
        if ev_max is not None and ev_float > float(ev_max):
            return False
        
        return True
    except (TypeError, ValueError):
        return False

def esta_dentro_do_horario(hora_jogo_str: str, horario_inicio: str, horario_fim: str) -> bool:
    """Verifica se o jogo está dentro do horário configurado"""
    try:
        # Parse da hora do jogo
        if 'T' in hora_jogo_str:
            # Formato ISO: 2025-01-15T20:30:00Z
            hora_jogo = datetime.fromisoformat(hora_jogo_str.replace('Z', '+00:00'))
        else:
            # Formato alternativo
            hora_jogo = datetime.strptime(hora_jogo_str, "%Y-%m-%d %H:%M:%S")
        
        # Converte para time (ignora data)
        hora_jogo_time = hora_jogo.time()
        
        # Parse dos horários de filtro
        h_ini = time.fromisoformat(horario_inicio)
        h_fim = time.fromisoformat(horario_fim)
        
        # Verifica se cruza meia-noite
        if h_ini <= h_fim:
            # Horário normal (ex: 19:00 - 23:00)
            return h_ini <= hora_jogo_time <= h_fim
        else:
            # Cruza meia-noite (ex: 22:00 - 06:00)
            return hora_jogo_time >= h_ini or hora_jogo_time <= h_fim
    
    except Exception as e:
        print(f"Erro ao verificar horário: {e}")
        return False

def esta_dentro_da_data(hora_jogo_str: str, data_inicio, data_fim) -> bool:
    """Verifica se o jogo está dentro do período de datas"""
    try:
        # Parse datetime do jogo (tz-aware UTC)
        if 'T' in hora_jogo_str:
            data_jogo_dt = datetime.fromisoformat(hora_jogo_str.replace('Z', '+00:00'))
        else:
            data_jogo_dt = datetime.strptime(hora_jogo_str, "%Y-%m-%d %H:%M:%S")
        if data_jogo_dt.tzinfo is None:
            data_jogo_dt = data_jogo_dt.replace(tzinfo=timezone.utc)

        # Comparação por data (sem timezone) usando a data em UTC
        data_jogo = data_jogo_dt.astimezone(timezone.utc).date()
        return data_inicio <= data_jogo <= data_fim
    
    except Exception as e:
        print(f"Erro ao verificar data: {e}")
        return False

def evento_valido(evento: Dict[str, Any], filtros: Dict[str, Any]) -> bool:
    """
    Valida se um evento atende aos filtros do usuário
    EV já vem convertido do parse da API
    """
    liga = evento.get("league")
    esporte = evento.get("sport")
    ev = evento.get("ev", 0)  # ← JÁ VEM CONVERTIDO DO PARSE
    odd = evento.get("bet365_odds", 0)
    hora_jogo = evento.get("commence_time") or evento.get("date")
    market_name = (evento.get("market_name") or "").lower()

    # Ignora mercados proibidos
    if any(x in market_name for x in MERCADOS_PROIBIDOS):
        return False

    # Ligas e esportes
    ligas_filtro = filtros.get("ligas")
    if ligas_filtro and liga not in ligas_filtro:
        return False
    esportes_filtro = filtros.get("esportes")
    if esportes_filtro and esporte not in esportes_filtro:
        return False

    # Odd válida
    if not odd_valida(odd):
        return False

    # EV faixa
    ev_min = filtros.get("ev_faixa_min")
    ev_max = filtros.get("ev_faixa_max")
    if not esta_dentro_do_ev(ev, ev_min, ev_max):
        return False

    # Horário
    h_ini = filtros.get("horario_inicio")
    h_fim = filtros.get("horario_fim")
    if h_ini and h_fim and hora_jogo:
        if not esta_dentro_do_horario(hora_jogo, h_ini, h_fim):
            return False

    # Data (período fixo)
    data_inicio_str = filtros.get("data_inicio")
    data_fim_str = filtros.get("data_fim")
    if data_inicio_str and data_fim_str and hora_jogo:
        try:
            data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
            data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
            if not esta_dentro_da_data(hora_jogo, data_inicio, data_fim):
                return False
        except Exception:
            return False

    return True

def calcular_janela_tempo_dinamica(filtro_dias: int, momento_scan: datetime = None) -> tuple:
    """
    Calcula a janela de tempo para filtros dinâmicos baseada no momento do scan.
    Retorna (inicio, fim) da janela de tempo.
    
    Args:
        filtro_dias: Número de dias para o filtro
        momento_scan: Momento do scan (default: agora)
    
    Returns:
        tuple: (inicio_janela, fim_janela) em UTC
    """
    if not filtro_dias or not isinstance(filtro_dias, int):
        return None, None
    
    if momento_scan is None:
        momento_scan = datetime.now(timezone.utc)
    
    # Janela: início do dia atual até o fim do dia + filtro_dias (UTC)
    inicio_do_dia_utc = momento_scan.replace(hour=0, minute=0, second=0, microsecond=0)
    fim_do_dia_utc = momento_scan.replace(hour=23, minute=59, second=59, microsecond=999999)
    limite = fim_do_dia_utc + timedelta(days=filtro_dias)
    
    return inicio_do_dia_utc, limite

def aplicar_filtros_dinamicos(evento: Dict[str, Any], filtros: Dict[str, Any], janela_tempo: tuple = None) -> bool:
    """
    Aplica filtros dinâmicos baseados em dias usando janela de tempo pré-calculada.
    
    Args:
        evento: Evento a ser filtrado
        filtros: Filtros do usuário
        janela_tempo: Tupla (inicio, fim) da janela de tempo (opcional)
    """
    filtro_dias = filtros.get("filtro_dias")
    if not filtro_dias or not isinstance(filtro_dias, int):
        return True
    
    try:
        hora_jogo_str = evento.get("commence_time") or evento.get("date")
        if not hora_jogo_str:
            return True

        # Parse da data/hora do jogo (tz-aware UTC)
        if 'T' in hora_jogo_str:
            data_jogo = datetime.fromisoformat(hora_jogo_str.replace('Z', '+00:00'))
        else:
            data_jogo = datetime.strptime(hora_jogo_str, "%Y-%m-%d %H:%M:%S")
        if data_jogo.tzinfo is None:
            data_jogo = data_jogo.replace(tzinfo=timezone.utc)

        # Usa janela pré-calculada ou calcula na hora (fallback)
        if janela_tempo:
            inicio_janela, fim_janela = janela_tempo
        else:
            # Fallback: calcula na hora (comportamento antigo)
            inicio_janela, fim_janela = calcular_janela_tempo_dinamica(filtro_dias)

        if inicio_janela is None or fim_janela is None:
            return True

        return inicio_janela <= data_jogo <= fim_janela
    
    except Exception as e:
        print(f"Erro ao aplicar filtros dinâmicos: {e}")
        return True

def validar_filtros_completos(filtros: Dict[str, Any]) -> bool:
    """Verifica se os filtros estão completos e válidos"""
    # Verifica campos obrigatórios
    if not filtros.get("bookmakers"):
        return False
    
    # Verifica EV mínimo
    ev_min = filtros.get("ev_faixa_min")
    if ev_min is None or ev_min < 0:
        return False
    
    # Verifica horários se fornecidos
    h_ini = filtros.get("horario_inicio")
    h_fim = filtros.get("horario_fim")
    if h_ini and h_fim:
        try:
            time.fromisoformat(h_ini)
            time.fromisoformat(h_fim)
        except ValueError:
            return False
    
    # Verifica datas se fornecidas
    data_inicio = filtros.get("data_inicio")
    data_fim = filtros.get("data_fim")
    if data_inicio and data_fim:
        try:
            datetime.strptime(data_inicio, "%Y-%m-%d")
            datetime.strptime(data_fim, "%Y-%m-%d")
        except ValueError:
            return False
    
    return True

def validar_filtros(evento, filtros_usuario, ligas_usuario, esportes_usuario, bookmakers_usuario):
    """
    Valida se um evento atende aos filtros do usuário
    """
    try:
        # Filtros básicos
        if not evento_valido(evento, filtros_usuario):
            return False
        
        # Filtros específicos do usuário
        if not validar_filtros_usuario(evento, filtros_usuario, ligas_usuario, esportes_usuario, bookmakers_usuario):
            return False
        
        return True
        
    except Exception as e:
        print(f"Erro na validação de filtros: {e}")
        return False

def validar_filtros_usuario(evento, filtros_usuario, ligas_usuario, esportes_usuario, bookmakers_usuario):
    """
    Valida filtros específicos do usuário
    NOTA: Para feed_american, ligas/esportes são validados em validar_filtros_americanos()
    """
    try:
        from config import FEED_ID
        
        # Para feed americano, NÃO valida ligas/esportes aqui
        # A validação é feita em validar_filtros_americanos() usando os slugs corretos da API
        if FEED_ID != 'feed_american':
            # Verifica ligas (apenas para feeds normais)
            if ligas_usuario and evento.get("league") not in ligas_usuario:
                return False
            
            # Verifica esportes (apenas para feeds normais)
            if esportes_usuario and evento.get("sport") not in esportes_usuario:
                return False
        
        # Verifica bookmakers (sempre aplica)
        if bookmakers_usuario and evento.get("bookmaker") not in bookmakers_usuario:
            return False
        
        return True
        
    except Exception as e:
        print(f"Erro na validação de filtros do usuário: {e}")
        return False

# ===== VALIDAÇÕES PARA FEED AMERICANO =====

def is_american_sport(sport_slug: str) -> bool:
    """
    Verifica se um esporte é americano baseado no slug da API
    Slugs corretos da API odds-api.io
    NOTA: 'football' (soccer) precisa validação extra de liga
    NOTA: API retorna com ESPAÇO, não hífen!
    """
    american_sports = [
        'american football',  # NFL, NCAAF (API retorna com espaço!)
        'basketball',         # NBA, WNBA, NCAA
        'baseball',           # MLB
        'ice hockey',         # NHL, AHL, ECHL (API retorna com espaço!)
    ]
    return sport_slug in american_sports

def is_american_league(league_name: str) -> bool:
    """
    Verifica se uma liga é americana
    Baseado nos league slugs reais da API odds-api.io
    """
    if not league_name:
        return False
    
    # Slugs de ligas americanas da API
    american_league_slugs = [
        'usa-nfl', 'usa-ncaa-regular-season',  # Football
        'usa-nba', 'usa-wnba', 'usa-ncaa-regular-season', 'usa-ncaa-women',  # Basketball
        'usa-mlb',  # Baseball
        'usa-nhl', 'usa-ahl', 'usa-echl',  # Ice Hockey
        'usa-mls', 'usa-usl-championship', 'usa-usl-league-one', 'usa-national-womens-soccer-league'  # Soccer
    ]
    
    # Converte league_name para lowercase e verifica
    league_lower = league_name.lower()
    return any(american_slug in league_lower for american_slug in american_league_slugs)

def validar_esporte_americano(evento: Dict[str, Any], feed_id: str) -> bool:
    """
    Valida se um evento é de esporte americano (para feed_american)
    Aceita apenas:
    - NFL/NCAAF (american football + liga americana)
    - NBA/WNBA/NCAA (basketball + liga americana)
    - MLB (baseball + liga americana)
    - NHL/AHL (ice hockey + liga americana)
    - MLS/USL (football/soccer + liga americana)
    """
    if feed_id != 'feed_american':
        return True  # Não aplica restrição para outros feeds
    
    sport_slug = evento.get('sport', '').lower()
    league_name = evento.get('league', '')
    
    # DEBUG: Log para verificar o que está sendo filtrado
    import logging
    logger = logging.getLogger(__name__)
    
    # American Football: SEMPRE validar liga (NFL, NCAAF)
    if sport_slug == 'american football':
        if is_american_league(league_name):
            logger.info(f"✅ Evento aceito - American Football: {league_name}")
            return True
        else:
            logger.info(f"❌ Evento rejeitado - American Football não americano: {league_name}")
            return False
    
    # Basketball: SEMPRE validar liga (NBA, WNBA, NCAA)
    # Rejeita ligas europeias (BNXT, ABA Liga, etc)
    if sport_slug == 'basketball':
        if is_american_league(league_name):
            logger.info(f"✅ Evento aceito - Basketball americano: {league_name}")
            return True
        else:
            logger.info(f"❌ Evento rejeitado - Basketball não americano: {league_name}")
            return False
    
    # Baseball: SEMPRE validar liga (MLB)
    if sport_slug == 'baseball':
        if is_american_league(league_name):
            logger.info(f"✅ Evento aceito - Baseball americano: {league_name}")
            return True
        else:
            logger.info(f"❌ Evento rejeitado - Baseball não americano: {league_name}")
            return False
    
    # Ice Hockey: SEMPRE validar liga (NHL, AHL, ECHL)
    if sport_slug == 'ice hockey':
        if is_american_league(league_name):
            logger.info(f"✅ Evento aceito - Ice Hockey americano: {league_name}")
            return True
        else:
            logger.info(f"❌ Evento rejeitado - Ice Hockey não americano: {league_name}")
            return False
    
    # Soccer (football): SEMPRE validar liga (MLS, USL)
    if sport_slug == 'football':
        if is_american_league(league_name):
            logger.info(f"✅ Evento aceito - Soccer americano: {league_name}")
            return True
        else:
            logger.info(f"❌ Evento rejeitado - Soccer não americano: {league_name}")
            return False
    
    # Qualquer outro esporte é rejeitado
    logger.info(f"❌ Evento rejeitado - Sport não americano: {sport_slug}")
    return False

def validar_player_prop(evento: Dict[str, Any], filtros_usuario: Dict[str, Any], feed_id: str) -> bool:
    """
    Valida se um player prop deve ser enviado
    
    - Feed Americano: apenas props de esportes/ligas americanas
    - Feeds Normais: props de qualquer esporte, mas respeitando filtros do usuário
    """
    # Verifica se é player prop
    if not evento.get('is_player_prop', False):
        return True  # Não é prop, não aplica validação
    
    # Verifica se usuário quer receber props
    include_props = filtros_usuario.get('include_props', False)
    
    # Feed americano: props sempre ativos por padrão
    if feed_id == 'feed_american':
        include_props = True
    
    if not include_props:
        return False
    
    # Feed americano: apenas esportes/ligas americanas
    if feed_id == 'feed_american':
        if not validar_esporte_americano(evento, feed_id):
            return False
    
    # Props devem respeitar mesmos filtros de liga/esporte
    # (isso já é feito em evento_valido())
    
    return True

def validar_filtros_americanos(evento: Dict[str, Any], filtros_usuario: Dict[str, Any], feed_id: str) -> bool:
    """
    Valida filtros específicos para feed americano
    """
    # Aplica validação de esporte americano
    if not validar_esporte_americano(evento, feed_id):
        return False
    
    # Aplica validação de player props
    if not validar_player_prop(evento, filtros_usuario, feed_id):
        return False
    
    return True