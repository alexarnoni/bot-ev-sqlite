"""
Comparador de Player Props para feed americano
"""
import re
from typing import Dict, List, Optional
from collections import defaultdict

def extract_player_props(odds_json: dict) -> List[Dict]:
    """
    Extrai player props de estrutura de odds da API
    
    Entrada: estrutura igual à da doc:
    { "bookmakers": { "BetMGM": [ { "name": "Player Props - Points", "odds": [ {"label":"LeBron James","hdp":27.5,"over":"1.90","under":"1.90"}, ... ] }, ... ] } }
    
    Saída: [{player, stat, line, bookmaker, over, under} ...]
    """
    props = []
    
    try:
        bookmakers_data = odds_json.get('bookmakers', {})
        
        for bookmaker_name, markets in bookmakers_data.items():
            if not isinstance(markets, list):
                continue
                
            for market in markets:
                market_name = market.get('name', '')
                odds_list = market.get('odds', [])
                
                # Verifica se é player prop
                if not _is_player_prop_market(market_name):
                    continue
                
                # Extrai tipo de stat
                stat_type = _extract_stat_type(market_name)
                if not stat_type:
                    continue
                
                # Processa cada odd (jogador)
                for odd_entry in odds_list:
                    if not isinstance(odd_entry, dict):
                        continue
                    
                    player = odd_entry.get('label', '').strip()
                    line = _parse_float(odd_entry.get('hdp', 0))
                    over_odd = _parse_float(odd_entry.get('over'))
                    under_odd = _parse_float(odd_entry.get('under'))
                    
                    # Valida dados obrigatórios
                    if not player or line is None or over_odd is None or under_odd is None:
                        continue
                    
                    # Filtra props que são totais de equipe (não individuais)
                    if _is_team_total(player):
                        continue
                    
                    props.append({
                        'player': player,
                        'stat': stat_type,
                        'line': line,
                        'bookmaker': bookmaker_name,
                        'over': over_odd,
                        'under': under_odd
                    })
    
    except Exception as e:
        print(f"Erro ao extrair player props: {e}")
    
    return props

def group_and_compare(items: List[Dict]) -> List[Dict]:
    """
    Agrupa por (player, stat, line) e seleciona best_over e best_under
    
    Saída: [{player, stat, line, best_over: {odd, bookmaker}, best_under: {odd, bookmaker}, all: [... por casa ...]}]
    """
    # Agrupa por chave única
    groups = defaultdict(list)
    
    for item in items:
        key = (item['player'], item['stat'], item['line'])
        groups[key].append(item)
    
    results = []
    
    for (player, stat, line), group_items in groups.items():
        # Encontra melhor over e under
        best_over = max(group_items, key=lambda x: x['over'])
        best_under = max(group_items, key=lambda x: x['under'])
        
        # Ordena todas as opções por odd (desc)
        all_options = sorted(group_items, key=lambda x: x['over'], reverse=True)
        
        results.append({
            'player': player,
            'stat': stat,
            'line': line,
            'best_over': {
                'odd': best_over['over'],
                'bookmaker': best_over['bookmaker']
            },
            'best_under': {
                'odd': best_under['under'],
                'bookmaker': best_under['bookmaker']
            },
            'all': all_options
        })
    
    return results

def render_props_message(results: List[Dict], top: int = 10) -> str:
    """
    Monta texto pronto pro Telegram: top N linhas
    
    Formato:
    "LeBron James — Points — linha 27.5
       Over 1.95 (BetMGM) | Under 1.92 (Betano)"
    
    Ordenação por maior best_over.odd (desc)
    """
    if not results:
        return "❌ Nenhum player prop encontrado"
    
    # Ordena por melhor over odd (desc)
    sorted_results = sorted(results, key=lambda x: x['best_over']['odd'], reverse=True)
    
    # Pega apenas os top N
    top_results = sorted_results[:top]
    
    lines = []
    
    for result in top_results:
        player = result['player']
        stat = result['stat']
        line = result['line']
        best_over = result['best_over']
        best_under = result['best_under']
        
        # Linha principal
        main_line = f"{player} — {stat} — linha {line}"
        
        # Linha de odds
        over_text = f"Over {best_over['odd']} ({best_over['bookmaker']})"
        under_text = f"Under {best_under['odd']} ({best_under['bookmaker']})"
        odds_line = f"   {over_text} | {under_text}"
        
        lines.append(main_line)
        lines.append(odds_line)
        lines.append("")  # Linha em branco
    
    return "\n".join(lines)

def _is_player_prop_market(market_name: str) -> bool:
    """
    Verifica se um mercado é de player props
    """
    if not market_name:
        return False
    
    market_lower = market_name.lower()
    
    # Palavras-chave de props
    prop_keywords = [
        'player props', 'player prop', 'props', 'player',
        'points', 'pts', 'rebounds', 'reb', 'assists', 'ast',
        'yards', 'yds', 'touchdowns', 'td', 'receptions', 'rec',
        'strikeouts', 'home runs', 'hits', 'rbi', 'goals',
        'shots', 'saves', 'blocks', 'steals', 'three pointers'
    ]
    
    # Verifica se contém alguma palavra-chave
    return any(keyword in market_lower for keyword in prop_keywords)

def _extract_stat_type(market_name: str) -> Optional[str]:
    """
    Extrai tipo de stat do nome do mercado
    """
    if not market_name:
        return None
    
    market_lower = market_name.lower()
    
    # Mapeamento de keywords para tipos
    stat_mapping = {
        'points': 'Points',
        'pts': 'Points',
        'rebounds': 'Rebounds',
        'reb': 'Rebounds',
        'assists': 'Assists',
        'ast': 'Assists',
        'yards': 'Yards',
        'yds': 'Yards',
        'passing yards': 'Passing Yards',
        'rushing yards': 'Rushing Yards',
        'receiving yards': 'Receiving Yards',
        'touchdowns': 'Touchdowns',
        'td': 'Touchdowns',
        'receptions': 'Receptions',
        'rec': 'Receptions',
        'strikeouts': 'Strikeouts',
        'home runs': 'Home Runs',
        'hits': 'Hits',
        'rbi': 'RBI',
        'stolen bases': 'Stolen Bases',
        'goals': 'Goals',
        'shots': 'Shots',
        'saves': 'Saves',
        'blocks': 'Blocks',
        'steals': 'Steals',
        'three pointers': 'Three Pointers',
        '3-pointers': 'Three Pointers'
    }
    
    # Busca por keywords no nome do mercado
    for keyword, stat_type in stat_mapping.items():
        if keyword in market_lower:
            return stat_type
    
    # Fallback: tenta extrair do nome completo
    if 'player props' in market_lower:
        # Remove "Player Props - " e pega o resto
        cleaned = market_lower.replace('player props -', '').replace('player props', '').strip()
        if cleaned:
            return cleaned.title()
    
    return None

def _parse_float(value) -> Optional[float]:
    """
    Converte string para float de forma segura
    """
    try:
        if value is None:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None

def _is_team_total(player: str) -> bool:
    """
    Verifica se é total de equipe (não individual)
    """
    if not player:
        return True
    
    player_lower = player.lower()
    
    # Palavras que indicam total de equipe
    team_indicators = [
        'total', 'spread', 'team total', 'team', 'overall',
        'combined', 'team over', 'team under'
    ]
    
    return any(indicator in player_lower for indicator in team_indicators)

# Funções de conveniência para uso externo
def process_odds_data(odds_json: dict, top: int = 10) -> str:
    """
    Processa dados de odds e retorna mensagem formatada
    """
    props = extract_player_props(odds_json)
    if not props:
        return "❌ Nenhum player prop encontrado"
    
    grouped = group_and_compare(props)
    return render_props_message(grouped, top)

def get_props_summary(odds_json: dict) -> Dict:
    """
    Retorna resumo dos props encontrados
    """
    props = extract_player_props(odds_json)
    grouped = group_and_compare(props)
    
    return {
        'total_props': len(props),
        'unique_combinations': len(grouped),
        'players': list(set(p['player'] for p in props)),
        'stats': list(set(p['stat'] for p in props)),
        'bookmakers': list(set(p['bookmaker'] for p in props))
    }
