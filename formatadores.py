"""
Formatadores para exibição de dados
"""
from typing import Union

def formatar_ev(ev: Union[float, int]) -> str:
    """
    Formata EV para exibição
    """
    try:
        ev_float = float(ev)
        ev_pct = ev_float * 100
        return f"{ev_pct:+.2f}%"
    except (TypeError, ValueError):
        return "0.00%"

def formatar_odd(odd: Union[float, int]) -> str:
    """
    Formata odd para exibição
    """
    try:
        odd_float = float(odd)
        return f"{odd_float:.2f}"
    except (TypeError, ValueError):
        return "0.00"

def formatar_stake(stake: Union[float, int]) -> str:
    """
    Formata stake para exibição
    """
    try:
        stake_float = float(stake)
        return f"{stake_float:.2f}u"
    except (TypeError, ValueError):
        return "0.00u"

def formatar_handicap(hdp: Union[float, int]) -> str:
    """
    Formata handicap para exibição
    """
    try:
        hdp_float = float(hdp)
        if hdp_float > 0:
            return f"+{hdp_float:.1f}"
        else:
            return f"{hdp_float:.1f}"
    except (TypeError, ValueError):
        return "0.0"

def formatar_total(total: Union[float, int]) -> str:
    """
    Formata total para exibição
    """
    try:
        total_float = float(total)
        return f"{total_float:.1f}"
    except (TypeError, ValueError):
        return "0.0"

def formatar_moeda(valor: Union[float, int], moeda: str = "R$") -> str:
    """
    Formata valor monetário
    """
    try:
        valor_float = float(valor)
        return f"{moeda} {valor_float:,.2f}".replace(",", ".")
    except (TypeError, ValueError):
        return f"{moeda} 0,00"

def formatar_tempo_segundos(segundos: int) -> str:
    """
    Formata tempo em segundos para formato legível
    """
    try:
        horas = segundos // 3600
        minutos = (segundos % 3600) // 60
        segs = segundos % 60
        
        if horas > 0:
            return f"{horas}h {minutos}m {segs}s"
        elif minutos > 0:
            return f"{minutos}m {segs}s"
        else:
            return f"{segs}s"
    except (TypeError, ValueError):
        return "0s"

def formatar_data_brasileira(data_str: str) -> str:
    """
    Formata data para formato brasileiro
    """
    try:
        from datetime import datetime
        
        # Parse da data
        if 'T' in data_str:
            data = datetime.fromisoformat(data_str.replace('Z', '+00:00'))
        else:
            data = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S")
        
        # Formata para brasileiro
        return data.strftime("%d/%m/%Y %H:%M")
        
    except Exception:
        return data_str

def formatar_nome_liga(liga: str) -> str:
    """
    Formata nome da liga para exibição
    """
    try:
        # Remove underscores e capitaliza
        liga_formatada = liga.replace("_", " ").title()
        
        # Ajustes específicos
        liga_formatada = liga_formatada.replace("Uefa", "UEFA")
        liga_formatada = liga_formatada.replace("Fifa", "FIFA")
        liga_formatada = liga_formatada.replace("Nba", "NBA")
        liga_formatada = liga_formatada.replace("Mls", "MLS")
        
        return liga_formatada
        
    except Exception:
        return liga

def formatar_nome_esporte(esporte: str) -> str:
    """
    Formata nome do esporte para exibição
    """
    try:
        esportes = {
            # Esportes principais
            'soccer': 'Futebol',
            'football': 'Futebol',
            'basketball': 'Basquete',
            'tennis': 'Tênis',
            'volleyball': 'Vôlei',
            'handball': 'Handebol',
            'americanfootball': 'Futebol Americano',
            'american football': 'Futebol Americano',
            'baseball': 'Baseball',
            'icehockey': 'Hockey',
            'ice hockey': 'Hockey',
            'cricket': 'Cricket',
            'rugby': 'Rugby',
            'rugby league': 'Rugby League',
            'rugby union': 'Rugby Union',
            
            # Esportes de combate
            'boxing': 'Boxe',
            'mma': 'MMA',
            'ufc': 'UFC',
            'kickboxing': 'Kickboxing',
            'muay thai': 'Muay Thai',
            'karate': 'Karatê',
            'taekwondo': 'Taekwondo',
            
            # Esportes de raquete
            'table tennis': 'Tênis de Mesa',
            'badminton': 'Badminton',
            'squash': 'Squash',
            'racquetball': 'Racquetball',
            
            # Esports
            'esports': 'Esports',
            'csgo': 'CS:GO',
            'counter-strike': 'Counter-Strike',
            'dota': 'Dota 2',
            'lol': 'League of Legends',
            'league of legends': 'League of Legends',
            'valorant': 'Valorant',
            'overwatch': 'Overwatch',
            'rocket league': 'Rocket League',
            
            # Esportes automobilísticos
            'formula 1': 'Fórmula 1',
            'f1': 'Fórmula 1',
            'motogp': 'MotoGP',
            'nascar': 'NASCAR',
            'indycar': 'IndyCar',
            'rally': 'Rally',
            'rallycross': 'Rallycross',
            
            # Outros esportes
            'golf': 'Golf',
            'darts': 'Dardos',
            'snooker': 'Snooker',
            'pool': 'Sinuca',
            'billiards': 'Bilhar',
            'australian football': 'Futebol Australiano',
            'afl': 'AFL',
            'futsal': 'Futsal',
            'softball': 'Softball'
        }
        
        return esportes.get(esporte.lower(), esporte.title())
        
    except Exception:
        return esporte

def formatar_nome_bookmaker(bookmaker: str) -> str:
    """
    Formata nome do bookmaker para exibição
    """
    try:
        bookmakers = {
            'bet365': 'Bet365',
            'pinnacle': 'Pinnacle',
            'betfair': 'Betfair',
            'sportingbet': 'Sportingbet',
            'betano': 'Betano',
            'betboo': 'Betboo',
            'betclic': 'Betclic',
            'betfred': 'Betfred',
            'unibet': 'Unibet',
            'betway': 'Betway'
        }
        
        return bookmakers.get(bookmaker.lower(), bookmaker.title())
        
    except Exception:
        return bookmaker

TRADUCAO_MERCADOS = {
    "spread": "Handicap Asiático",
    "point spread": "Handicap",
    "spread ht": "Handicap HT",
    "ml": "Moneyline",
    "moneyline": "Moneyline",
    "ou": "Over/Under",
    "totals": "Mais/Menos",
    "total points": "Total de Pontos",
    "total games": "Total de Games",
    "games": "Games",
    "over/under sets": "Total de Sets",
    "total maps": "Total de Mapas",
    "map winner": "Vencedor do Mapa",
    "rounds": "Rounds",
    "dnb": "Empate Anula",
    "btts": "Ambos Marcam",
    "team_total": "Total do Time",
    "team total home": "Total Time da Casa",
    "team total away": "Total Time Visitante",
    "anytime_goalscorer": "Marcar a Qualquer Momento",
    "bookings": "Cartões",
    "bookings spread": "Handicap de Cartões",
    "bookings totals": "Total de Cartões",
    "booking": "Cartões",
    "booking spread": "Handicap de Cartões",
    "booking totals": "Total de Cartões",
    "corners": "Cantos",
    "corners spread": "Handicap de Cantos",
    "corners totals": "Total de Cantos",
    "corner": "Cantos",
    "corner spread": "Handicap de Cantos",
    "corner totals": "Total de Cantos",
    "match winner": "Vencedor da Partida",
    "winner": "Vencedor",
    "set winner": "Vencedor do Set",
    "handicap games": "Handicap de Games",
    "run line": "Handicap de Corridas",
    "total runs": "Total de Corridas",
    "fight winner": "Vencedor da Luta",
    "method of victory": "Método da Vitória",
    "round betting": "Aposta por Round",
    "map handicap": "Handicap Asiático",
    "handicap": "Handicap",
    "h2h": "Moneyline",
    "spreads": "Handicap",
    "total": "Total",
    "over/under": "Over/Under"
}

TRADUCAO_LADOS = {
    "home": "Casa",
    "away": "Fora",
    "draw": "Empate",
    "over": "Mais de",
    "under": "Menos de"
}

def tipo_total_por_esporte(esporte):
    """
    Define o tipo de unidade para cada esporte
    """
    esporte_lower = esporte.lower()
    
    # Esportes que usam GOLS
    esportes_gols = [
        "soccer", "football", "handball", "futsal", "futebol"
    ]
    
    # Esportes que usam PONTOS
    esportes_pontos = [
        "basketball", "volleyball", "american football", "americanfootball", 
        "rugby", "rugby league", "rugby union", "australian football", "afl",
        "golf", "darts", "snooker", "pool", "billiards"
    ]
    
    # Esportes que usam GAMES/SETS
    esportes_games = [
        "tennis", "table tennis", "badminton", "squash", "racquetball"
    ]
    
    # Esportes que usam CORRIDAS
    esportes_corridas = [
        "baseball", "softball"
    ]
    
    # Esportes que usam ROUNDS
    esportes_rounds = [
        "boxing", "mma", "ufc", "kickboxing", "muay thai", "karate", "taekwondo"
    ]
    
    # Esportes que usam MAPAS
    esportes_mapas = [
        "esports", "csgo", "counter-strike", "dota", "lol", "league of legends",
        "valorant", "overwatch", "rocket league"
    ]
    
    # Esportes que usam TEMPO
    esportes_tempo = [
        "formula 1", "f1", "motogp", "nascar", "indycar", "rally", "rallycross"
    ]
    
    if esporte_lower in esportes_gols:
        return "Gols"
    elif esporte_lower in esportes_pontos:
        return "Pontos"
    elif esporte_lower in esportes_games:
        return "Games"
    elif esporte_lower in esportes_corridas:
        return "Corridas"
    elif esporte_lower in esportes_rounds:
        return "Rounds"
    elif esporte_lower in esportes_mapas:
        return "Mapas"
    elif esporte_lower in esportes_tempo:
        return "Tempo"
    else:
        return "Pontos"  # Fallback genérico

def formatar_handicap_final(hdp, bet_side):
    try:
        hdp = float(hdp)
    except Exception:
        hdp = 0.0
    # Para zero, sempre mostrar "0.0"
    if hdp == 0 or hdp == -0.0:
        return "0.0"
    # Para linha, segue a lógica Bet365: se bet_side for "home", mantém o sinal do hdp;
    # se for "away", inverte o sinal para mostrar o valor positivo para o time fora.
    # A linha exibida é SEMPRE positiva para o time correspondente.
    if bet_side == "away":
        hdp = -hdp
    # Sempre mostrar o sinal explícito, até para negativo
    return f"{hdp:+.2f}".replace(".00", ".0") # ex: +1.5 -> 1.5, -1.5 -> -1.5

def get_hdp(evento):
    """Busca o valor do handicap (hdp) em todos os campos possíveis."""
    hdp = (
        evento.get("market", {}).get("hdp")
        or evento.get("hdp")
        or evento.get("bookmakerOdds", {}).get("hdp")
        or 0
    )
    return hdp

def extrair_linha_mercado(evento):
    """
    Extrai linha do mercado (hdp ou total)
    """
    hdp = evento.get("market", {}).get("hdp") or evento.get("hdp")
    total = evento.get("market", {}).get("total") or evento.get("total")
    bet_side = (evento.get("betSide") or evento.get("bet_side") or "").lower()

    def aplicar_sinal(valor):
        try:
            valor = float(valor)
        except Exception:
            return str(valor)
        return f"{valor:g}"

    if hdp is not None:
        if isinstance(hdp, list):
            return "/".join([aplicar_sinal(x) for x in hdp])
        return aplicar_sinal(hdp)
    if total is not None:
        if isinstance(total, list):
            return "/".join([aplicar_sinal(x) for x in total])
        return aplicar_sinal(total)
    return ""

def _traduzir_tipo_prop(tipo_prop: str, esporte: str) -> str:
    """
    Traduz tipo de player prop para português
    """
    tipo_lower = tipo_prop.lower()
    esporte_lower = esporte.lower()
    
    # Traduções específicas por esporte
    if esporte_lower in ['basketball', 'basquete']:
        props_basketball = {
            'points': 'Pontos',
            'rebounds': 'Rebotes',
            'assists': 'Assistências',
            'steals': 'Roubos',
            'blocks': 'Bloqueios',
            'turnovers': 'Perdas de Bola',
            'threes': 'Arremessos de 3',
            'field goals': 'Arremessos de Campo',
            'free throws': 'Lances Livres'
        }
        return props_basketball.get(tipo_lower, tipo_prop.title())
    
    elif esporte_lower in ['soccer', 'football', 'futebol']:
        props_futebol = {
            'goals': 'Gols',
            'assists': 'Assistências',
            'shots': 'Chutes',
            'shots on target': 'Chutes no Gol',
            'passes': 'Passes',
            'tackles': 'Desarmes',
            'fouls': 'Faltas',
            'cards': 'Cartões',
            'corners': 'Cantos'
        }
        return props_futebol.get(tipo_lower, tipo_prop.title())
    
    elif esporte_lower in ['americanfootball', 'american football', 'futebol americano']:
        props_nfl = {
            'passing yards': 'Jardas de Passe',
            'rushing yards': 'Jardas de Corrida',
            'receiving yards': 'Jardas de Recepção',
            'passing touchdowns': 'Touchdowns de Passe',
            'rushing touchdowns': 'Touchdowns de Corrida',
            'receiving touchdowns': 'Touchdowns de Recepção',
            'receptions': 'Recepções',
            'completions': 'Completos',
            'interceptions': 'Interceptações',
            'sacks': 'Sacks'
        }
        return props_nfl.get(tipo_lower, tipo_prop.title())
    
    elif esporte_lower in ['tennis', 'tenis']:
        props_tennis = {
            'aces': 'Aces',
            'double faults': 'Duplas Faltas',
            'winners': 'Winners',
            'unforced errors': 'Erros Não Forçados',
            'first serve percentage': 'Primeiro Saque %',
            'break points': 'Break Points',
            'games': 'Games',
            'sets': 'Sets'
        }
        return props_tennis.get(tipo_lower, tipo_prop.title())
    
    elif esporte_lower in ['baseball', 'beisebol']:
        props_baseball = {
            'hits': 'Hits',
            'runs': 'Corridas',
            'rbis': 'RBIs',
            'home runs': 'Home Runs',
            'strikeouts': 'Strikeouts',
            'walks': 'Bases por Bola',
            'stolen bases': 'Bases Roubadas',
            'innings pitched': 'Entradas Lançadas'
        }
        return props_baseball.get(tipo_lower, tipo_prop.title())
    
    # Traduções genéricas
    props_genericos = {
        'points': 'Pontos',
        'goals': 'Gols',
        'assists': 'Assistências',
        'shots': 'Chutes',
        'saves': 'Defesas',
        'fouls': 'Faltas',
        'cards': 'Cartões',
        'minutes': 'Minutos',
        'yards': 'Jardas',
        'touchdowns': 'Touchdowns',
        'receptions': 'Recepções',
        'runs': 'Corridas',
        'hits': 'Hits',
        'strikeouts': 'Strikeouts'
    }
    
    return props_genericos.get(tipo_lower, tipo_prop.title())

def formatar_market_name(market: str, hdp: float = None, total: float = None, bet_side: str = '', aposta: dict = None) -> str:
    """
    Formata nome do mercado para exibição usando a lógica do bot antigo
    """
    try:
        if not aposta:
            return market.title()
        
        # Usa a função montar_nome_mercado do bot antigo
        return montar_nome_mercado(aposta)
        
    except Exception:
        return market.title()

def montar_nome_mercado(evento):
    """
    Função do bot antigo para montar nome do mercado
    """
    nome_raw = (evento.get("market", {}).get("name") or evento.get("market_name") or evento.get("market_type") or "").lower()
    nome_mercado_pt = TRADUCAO_MERCADOS.get(nome_raw, nome_raw.title())
    lado = (evento.get("betSide") or evento.get("bet_side") or "").lower()
    esporte = (evento.get("event", {}).get("sport") or evento.get("sport") or "").lower()
    time_home = evento.get("event", {}).get("home") or evento.get("home")
    time_away = evento.get("event", {}).get("away") or evento.get("away")
    lado_pt = TRADUCAO_LADOS.get(lado, "")
    
    def traduzir_bet_side(bet_side_str):
        """Traduz bet_side para português"""
        if not bet_side_str:
            return bet_side_str
        traducoes = {
            'draw': 'Empate',
            'home': time_home or 'Casa',
            'away': time_away or 'Fora',
            'over': 'Mais de',
            'under': 'Menos de'
        }
        return traducoes.get(bet_side_str.lower().strip(), bet_side_str)

    # HANDICAP/SPREAD/RUN LINE
    if any(k in nome_raw for k in ["handicap", "spread", "run line", "line"]):
        hdp = get_hdp(evento)
        valor_hdp = formatar_handicap_final(hdp, lado)
        
        bet_side_display = evento.get('bet_side', '')
        if bet_side_display:
            return f"{nome_mercado_pt} — {bet_side_display} {valor_hdp}"
        elif lado == "home":
            return f"{nome_mercado_pt} — {time_home} {valor_hdp}"
        elif lado == "away":
            return f"{nome_mercado_pt} — {time_away} {valor_hdp}"
        else:
            return f"{nome_mercado_pt} {valor_hdp}"

    # TEAM TOTAL
    if nome_raw.startswith("team total home"):
        nome_time = time_home
        tipo = tipo_total_por_esporte(esporte)
        hdp = get_hdp(evento)
        try:
            valor_hdp = float(hdp)
        except Exception:
            valor_hdp = hdp
        if lado == "home":
            return f"Mais de {valor_hdp} {tipo} do {nome_time}"
        elif lado == "away":
            return f"Menos de {valor_hdp} {tipo} do {nome_time}"
        else:
            return f"Total de {tipo} do {nome_time} {valor_hdp}"

    if nome_raw.startswith("team total away"):
        nome_time = time_away
        tipo = tipo_total_por_esporte(esporte)
        hdp = get_hdp(evento)
        try:
            valor_hdp = float(hdp)
        except Exception:
            valor_hdp = hdp
        if lado == "home":
            return f"Mais de {valor_hdp} {tipo} do {nome_time}"
        elif lado == "away":
            return f"Menos de {valor_hdp} {tipo} do {nome_time}"
        else:
            return f"Total de {tipo} do {nome_time} {valor_hdp}"

    # TOTALS (Mais/Menos etc)
    if (
        "totals" in nome_raw
        or nome_raw.startswith("total")
        or nome_raw.startswith("goals over/under")
        or nome_raw.startswith("corners totals")
        or nome_raw.startswith("bookings totals")
        or nome_raw.startswith("total maps")
        or nome_raw.startswith("totals ht")
        or "corner" in nome_raw
        or "booking" in nome_raw
        or "maps" in nome_raw
    ):
        tipo = tipo_total_por_esporte(esporte)
        if "corner" in nome_raw:
            tipo = "Cantos"
        elif "booking" in nome_raw:
            tipo = "Cartões"
        elif "maps" in nome_raw:
            tipo = "Mapas"
        hdp = get_hdp(evento)
        try:
            valor_hdp = float(hdp)
        except Exception:
            valor_hdp = hdp

        # Aqui faz a tradução para Mais de/Menos de
        if lado in ["home", "away"]:
            lado_pt = "Mais de" if lado == "home" else "Menos de"
            return f"{lado_pt} {valor_hdp} {tipo}"

        if lado in ["over", "under"]:
            lado_pt = TRADUCAO_LADOS.get(lado, "")
            return f"{lado_pt} {valor_hdp} {tipo}"
        
        # Se não conseguiu determinar o lado, tenta inferir do bet_side
        bet_side_display = evento.get('bet_side', '').lower()
        if 'over' in bet_side_display or 'mais' in bet_side_display:
            lado_pt = "Mais de"
        elif 'under' in bet_side_display or 'menos' in bet_side_display:
            lado_pt = "Menos de"
        else:
            # Fallback: assume "Mais de" se não conseguir determinar
            lado_pt = "Mais de"
        
        return f"{lado_pt} {valor_hdp} {tipo}"

    # MONEYLINE (ML, Moneyline)
    if nome_raw in ["ml", "moneyline", "h2h", "match winner", "match result"]:
        bet_side_display = evento.get('bet_side', '')
        
        if bet_side_display:
            bet_side_traduzido = traduzir_bet_side(bet_side_display)
            return f"{nome_mercado_pt} ({bet_side_traduzido})"
        elif lado == "home":
            return f"{nome_mercado_pt} ({time_home})"
        elif lado == "away":
            return f"{nome_mercado_pt} ({time_away})"
        elif lado == "draw":
            return f"{nome_mercado_pt} (Empate)"
        else:
            return nome_mercado_pt
        
    # PLAYER PROPS (ex: Player Props - Nome (Tipo))
    if "player props" in nome_raw or "player" in nome_raw.split()[0]:
        try:
            # Extrai jogador e tipo da prop do market name
            # Formato: "Player Props - Jogador (Tipo)"
            if " - " in nome_raw:
                prop_part = nome_raw.split(" - ", 1)[1]  # "myles turner (points)"
                
                # Separa jogador e tipo
                if "(" in prop_part and ")" in prop_part:
                    jogador = prop_part.split("(")[0].strip().title()
                    tipo_prop_raw = prop_part.split("(")[1].replace(")", "").strip()
                    
                    # Traduz o tipo de prop
                    tipo_prop = _traduzir_tipo_prop(tipo_prop_raw, esporte)
                    
                    # Pega o valor do handicap
                    hdp = get_hdp(evento)
                    try:
                        valor_hdp = float(hdp)
                    except Exception:
                        valor_hdp = hdp
                    
                    # Determina Mais/Menos baseado no lado
                    if lado == "home":
                        lado_pt = "Mais de"
                    elif lado == "away":
                        lado_pt = "Menos de"
                    else:
                        lado_pt = TRADUCAO_LADOS.get(lado, "")
                    return f"{jogador} - {lado_pt} {valor_hdp} {tipo_prop}"
        except Exception:
            pass  # fallback para o código existente abaixo

    # FALLBACK: nome do mercado + linha se houver
    linha = extrair_linha_mercado(evento)
    if linha:
        return f"{nome_mercado_pt} {linha}"

    return nome_mercado_pt

def formatar_nome_pais(pais: str) -> str:
    """
    Traduz nome do país para português
    """
    try:
        paises = {
            'united states': 'Estados Unidos',
            'usa': 'Estados Unidos',
            'united kingdom': 'Reino Unido',
            'uk': 'Reino Unido',
            'england': 'Inglaterra',
            'spain': 'Espanha',
            'germany': 'Alemanha',
            'france': 'França',
            'italy': 'Itália',
            'netherlands': 'Holanda',
            'portugal': 'Portugal',
            'brazil': 'Brasil',
            'argentina': 'Argentina',
            'mexico': 'México',
            'chile': 'Chile',
            'colombia': 'Colômbia',
            'peru': 'Peru',
            'uruguay': 'Uruguai',
            'ecuador': 'Equador',
            'venezuela': 'Venezuela',
            'bolivia': 'Bolívia',
            'paraguay': 'Paraguai',
            'russia': 'Rússia',
            'turkey': 'Turquia',
            'greece': 'Grécia',
            'belgium': 'Bélgica',
            'switzerland': 'Suíça',
            'austria': 'Áustria',
            'poland': 'Polônia',
            'croatia': 'Croácia',
            'serbia': 'Sérvia',
            'romania': 'Romênia',
            'bulgaria': 'Bulgária',
            'hungary': 'Hungria',
            'norway': 'Noruega',
            'sweden': 'Suécia',
            'denmark': 'Dinamarca',
            'finland': 'Finlândia',
            'japan': 'Japão',
            'china': 'China',
            'australia': 'Austrália',
            'canada': 'Canadá',
            'puerto rico': 'Porto Rico',
            'south korea': 'Coreia do Sul',
            'south africa': 'África do Sul',
            'egypt': 'Egito',
            'morocco': 'Marrocos',
            'tunisia': 'Tunísia',
            'algeria': 'Argélia',
            'nigeria': 'Nigéria',
            'ghana': 'Gana',
            'senegal': 'Senegal',
            'cameroon': 'Camarões',
            'ivory coast': 'Costa do Marfim',
            'mali': 'Mali',
            'burkina faso': 'Burkina Faso',
            'guinea': 'Guiné',
            'madagascar': 'Madagascar',
            'mauritius': 'Maurício',
            'seychelles': 'Seicheles',
            'comoros': 'Comores',
            'djibouti': 'Djibuti',
            'eritrea': 'Eritreia',
            'ethiopia': 'Etiópia',
            'kenya': 'Quênia',
            'tanzania': 'Tanzânia',
            'uganda': 'Uganda',
            'rwanda': 'Ruanda',
            'burundi': 'Burundi',
            'somalia': 'Somália',
            'sudan': 'Sudão',
            'south sudan': 'Sudão do Sul',
            'chad': 'Chade',
            'central african republic': 'República Centro-Africana',
            'congo': 'Congo',
            'democratic republic of the congo': 'República Democrática do Congo',
            'gabon': 'Gabão',
            'equatorial guinea': 'Guiné Equatorial',
            'são tomé and príncipe': 'São Tomé e Príncipe',
            'angola': 'Angola',
            'zambia': 'Zâmbia',
            'zimbabwe': 'Zimbábue',
            'botswana': 'Botsuana',
            'namibia': 'Namíbia',
            'lesotho': 'Lesoto',
            'swaziland': 'Suazilândia',
            'mozambique': 'Moçambique',
            'malawi': 'Malawi',
            'madagascar': 'Madagascar',
            'mauritius': 'Maurício',
            'seychelles': 'Seicheles',
            'comoros': 'Comores',
            'mayotte': 'Mayotte',
            'réunion': 'Reunião',
            'french southern territories': 'Territórios Franceses do Sul',
            'british indian ocean territory': 'Território Britânico do Oceano Índico',
            'south georgia and the south sandwich islands': 'Geórgia do Sul e Ilhas Sandwich do Sul',
            'bouvet island': 'Ilha Bouvet',
            'heard island and mcdonald islands': 'Ilha Heard e Ilhas McDonald',
            'french polynesia': 'Polinésia Francesa',
            'new caledonia': 'Nova Caledônia',
            'vanuatu': 'Vanuatu',
            'fiji': 'Fiji',
            'tonga': 'Tonga',
            'samoa': 'Samoa',
            'american samoa': 'Samoa Americana',
            'cook islands': 'Ilhas Cook',
            'niue': 'Niue',
            'tokelau': 'Tokelau',
            'wallis and futuna': 'Wallis e Futuna',
            'tuvalu': 'Tuvalu',
            'kiribati': 'Kiribati',
            'nauru': 'Nauru',
            'palau': 'Palau',
            'marshall islands': 'Ilhas Marshall',
            'micronesia': 'Micronésia',
            'guam': 'Guam',
            'northern mariana islands': 'Ilhas Marianas do Norte',
            'pitcairn islands': 'Ilhas Pitcairn',
            'norfolk island': 'Ilha Norfolk',
            'christmas island': 'Ilha Christmas',
            'cocos islands': 'Ilhas Cocos',
            'ashmore and cartier islands': 'Ilhas Ashmore e Cartier',
            'coral sea islands': 'Ilhas do Mar de Coral',
            'antarctica': 'Antártica',
            'french southern and antarctic lands': 'Terras Austrais e Antárticas Francesas',
            'svalbard and jan mayen': 'Svalbard e Jan Mayen',
            'greenland': 'Groenlândia',
            'faroe islands': 'Ilhas Faroé',
            'isle of man': 'Ilha de Man',
            'jersey': 'Jersey',
            'guernsey': 'Guernsey',
            'aland islands': 'Ilhas Åland',
            'gibraltar': 'Gibraltar',
            'ceuta': 'Ceuta',
            'melilla': 'Melilla',
            'canary islands': 'Ilhas Canárias',
            'madeira': 'Madeira',
            'azores': 'Açores',
            'balearic islands': 'Ilhas Baleares',
            'corsica': 'Córsega',
            'sardinia': 'Sardenha',
            'sicily': 'Sicília',
            'crete': 'Creta',
            'cyprus': 'Chipre',
            'malta': 'Malta',
            'iceland': 'Islândia',
            'ireland': 'Irlanda',
            'luxembourg': 'Luxemburgo',
            'liechtenstein': 'Liechtenstein',
            'monaco': 'Mônaco',
            'san marino': 'San Marino',
            'vatican city': 'Vaticano',
            'andorra': 'Andorra',
            'slovenia': 'Eslovênia',
            'slovakia': 'Eslováquia',
            'czech republic': 'República Tcheca',
            'czechia': 'República Tcheca',
            'estonia': 'Estônia',
            'latvia': 'Letônia',
            'lithuania': 'Lituânia',
            'belarus': 'Bielorrússia',
            'moldova': 'Moldávia',
            'ukraine': 'Ucrânia',
            'georgia': 'Geórgia',
            'armenia': 'Armênia',
            'azerbaijan': 'Azerbaijão',
            'kazakhstan': 'Cazaquistão',
            'uzbekistan': 'Uzbequistão',
            'turkmenistan': 'Turcomenistão',
            'tajikistan': 'Tajiquistão',
            'kyrgyzstan': 'Quirguistão',
            'afghanistan': 'Afeganistão',
            'pakistan': 'Paquistão',
            'india': 'Índia',
            'bangladesh': 'Bangladesh',
            'sri lanka': 'Sri Lanka',
            'maldives': 'Maldivas',
            'nepal': 'Nepal',
            'bhutan': 'Butão',
            'myanmar': 'Mianmar',
            'thailand': 'Tailândia',
            'laos': 'Laos',
            'vietnam': 'Vietnã',
            'cambodia': 'Camboja',
            'malaysia': 'Malásia',
            'singapore': 'Singapura',
            'brunei': 'Brunei',
            'indonesia': 'Indonésia',
            'philippines': 'Filipinas',
            'taiwan': 'Taiwan',
            'hong kong': 'Hong Kong',
            'macau': 'Macau',
            'mongolia': 'Mongólia',
            'north korea': 'Coreia do Norte',
            'iran': 'Irã',
            'iraq': 'Iraque',
            'syria': 'Síria',
            'lebanon': 'Líbano',
            'jordan': 'Jordânia',
            'israel': 'Israel',
            'palestine': 'Palestina',
            'saudi arabia': 'Arábia Saudita',
            'yemen': 'Iêmen',
            'oman': 'Omã',
            'united arab emirates': 'Emirados Árabes Unidos',
            'qatar': 'Catar',
            'bahrain': 'Bahrein',
            'kuwait': 'Kuwait',
            'cyprus': 'Chipre',
            'trinidad and tobago': 'Trinidad e Tobago',
            'barbados': 'Barbados',
            'saint lucia': 'Santa Lúcia',
            'saint vincent and the grenadines': 'São Vicente e Granadinas',
            'grenada': 'Granada',
            'antigua and barbuda': 'Antígua e Barbuda',
            'dominica': 'Dominica',
            'saint kitts and nevis': 'São Cristóvão e Nevis',
            'jamaica': 'Jamaica',
            'haiti': 'Haiti',
            'dominican republic': 'República Dominicana',
            'cuba': 'Cuba',
            'belize': 'Belize',
            'guatemala': 'Guatemala',
            'honduras': 'Honduras',
            'el salvador': 'El Salvador',
            'nicaragua': 'Nicarágua',
            'costa rica': 'Costa Rica',
            'panama': 'Panamá',
            'guyana': 'Guiana',
            'suriname': 'Suriname',
            'french guiana': 'Guiana Francesa',
            'vatican': 'Vaticano',
            'holy see': 'Vaticano',
            'palestinian territories': 'Territórios Palestinos',
            'western sahara': 'Saara Ocidental',
            'somaliland': 'Somalilândia',
            'transnistria': 'Transnístria',
            'abkhazia': 'Abecásia',
            'south ossetia': 'Ossétia do Sul',
            'nagorno-karabakh': 'Nagorno-Karabakh',
            'northern cyprus': 'Chipre do Norte',
            'taiwan': 'Taiwan',
            'hong kong': 'Hong Kong',
            'macau': 'Macau',
            'tibet': 'Tibet',
            'xinjiang': 'Xinjiang',
            'inner mongolia': 'Mongólia Interior',
            'manchuria': 'Manchúria',
            'kashmir': 'Caxemira',
            'kurdistan': 'Curdistão',
            'basque country': 'País Basco',
            'catalonia': 'Catalunha',
            'scotland': 'Escócia',
            'wales': 'País de Gales',
            'northern ireland': 'Irlanda do Norte',
            'cornwall': 'Cornualha',
            'brittany': 'Bretanha',
            'corsica': 'Córsega',
            'sardinia': 'Sardenha',
            'sicily': 'Sicília',
            'south tyrol': 'Tirol do Sul',
            'flanders': 'Flandres',
            'wallonia': 'Valônia',
            'swiss romandy': 'Romandia Suíça',
            'tessin': 'Ticino',
            'grisons': 'Grisões',
            'valais': 'Valais',
            'bern': 'Berna',
            'zurich': 'Zurique',
            'basel': 'Basileia',
            'geneva': 'Genebra',
            'lausanne': 'Lausana',
            'lucerne': 'Lucerna',
            'st. gallen': 'São Galo',
            'thurgau': 'Turgóvia',
            'aargau': 'Argóvia',
            'solothurn': 'Soleura',
            'basel-landschaft': 'Basileia-Campo',
            'basel-stadt': 'Basileia-Cidade',
            'schaffhausen': 'Schaffhausen',
            'appenzell ausserrhoden': 'Appenzell Exterior',
            'appenzell innerrhoden': 'Appenzell Interior',
            'st. gallen': 'São Galo',
            'graubünden': 'Grisões',
            'glarus': 'Glarus',
            'zug': 'Zug',
            'schwyz': 'Schwyz',
            'uri': 'Uri',
            'nidwalden': 'Nidwalden',
            'obwalden': 'Obwalden',
            'lucerne': 'Lucerna',
            'bern': 'Berna',
            'fribourg': 'Friburgo',
            'neuchâtel': 'Neuchâtel',
            'jura': 'Jura',
            'vaud': 'Vaud',
            'geneva': 'Genebra',
            'valais': 'Valais',
            'ticino': 'Ticino'
        }
        
        return paises.get(pais.lower(), pais.title())
        
    except Exception:
        return pais.title()