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
            'soccer': 'Futebol',
            'basketball': 'Basquete',
            'tennis': 'Tênis',
            'volleyball': 'Vôlei',
            'handball': 'Handebol',
            'americanfootball': 'Futebol Americano',
            'baseball': 'Baseball',
            'icehockey': 'Hockey',
            'cricket': 'Cricket',
            'rugby': 'Rugby'
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

def formatar_market_name(market: str) -> str:
    """
    Formata nome do mercado para exibição
    """
    try:
        mercados = {
            'h2h': 'Resultado Final',
            'spreads': 'Handicap',
            'totals': 'Total de Gols',
            'moneyline': 'Linha de Dinheiro',
            'point_spread': 'Spread de Pontos',
            'total_points': 'Total de Pontos'
        }
        
        return mercados.get(market.lower(), market.title())
        
    except Exception:
        return market