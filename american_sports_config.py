"""
Configuração específica para esportes americanos
"""
from typing import List, Dict, Set

# Esportes americanos suportados (identificadores CORRETOS da API odds-api.io)
AMERICAN_SPORTS = {
    'NFL': 'american-football',
    'College Football': 'american-football', 
    'NBA': 'basketball',
    'WNBA': 'basketball',
    'NCAA Basketball': 'basketball',
    'MLB': 'baseball',
    'NHL': 'ice-hockey',
    'AHL': 'ice-hockey',
    'MLS': 'football',  # Soccer nos EUA
    'USL Championship': 'football'
}

# Ligas americanas principais (baseado em league slugs da API odds-api.io)
AMERICAN_LEAGUES = [
    # American Football
    'USA - NFL',
    'USA - NCAA, Regular Season',
    'usa-nfl',
    'usa-ncaa-regular-season',
    
    # Basketball
    'USA - NBA',
    'USA - WNBA', 
    'USA - NCAA, Regular Season',
    'USA - NCAA Women',
    'usa-nba',
    'usa-wnba',
    
    # Baseball
    'USA - MLB',
    'usa-mlb',
    
    # Ice Hockey
    'USA - NHL',
    'USA - AHL',
    'USA - ECHL',
    'usa-nhl',
    'usa-ahl',
    'usa-echl',
    
    # Soccer (Football)
    'USA - MLS',
    'USA - USL Championship',
    'USA - USL League One',
    'USA - National Womens Soccer League',
    'usa-mls',
    'usa-usl-championship',
    'usa-usl-league-one'
]

# Player Props principais por esporte
PLAYER_PROPS_BY_SPORT = {
    'americanfootball_nfl': [
        'Passing Yards',
        'Rushing Yards', 
        'Receiving Yards',
        'Touchdowns',
        'Receptions',
        'Completions',
        'Interceptions'
    ],
    'americanfootball_ncaaf': [
        'Passing Yards',
        'Rushing Yards',
        'Receiving Yards', 
        'Touchdowns',
        'Receptions',
        'Completions'
    ],
    'basketball_nba': [
        'Points',
        'Rebounds',
        'Assists',
        'Steals',
        'Blocks',
        'Three Pointers',
        'Double-Double',
        'Triple-Double'
    ],
    'basketball_wnba': [
        'Points',
        'Rebounds', 
        'Assists',
        'Steals',
        'Blocks',
        'Three Pointers'
    ],
    'baseball_mlb': [
        'Strikeouts',
        'Home Runs',
        'Hits',
        'RBIs',
        'Runs',
        'Total Bases',
        'Stolen Bases'
    ],
    'baseball_milb': [
        'Strikeouts',
        'Home Runs',
        'Hits',
        'RBIs',
        'Runs'
    ],
    'soccer_usa_mls': [
        'Goals',
        'Assists',
        'Shots',
        'Shots on Target',
        'Yellow Cards',
        'Red Cards'
    ],
    'soccer_usa_usl': [
        'Goals',
        'Assists',
        'Shots',
        'Shots on Target'
    ]
}

def is_american_sport(sport_slug: str) -> bool:
    """
    Verifica se um esporte é americano baseado no slug da API
    """
    return sport_slug in AMERICAN_SPORTS.values()

def is_american_league(league_name: str) -> bool:
    """
    Verifica se uma liga é americana
    """
    if not league_name:
        return False
    
    # Verifica se contém alguma das ligas americanas
    return any(american_league in league_name for american_league in AMERICAN_LEAGUES)

def get_american_sports_list() -> List[str]:
    """
    Retorna lista de esportes americanos para exibição
    """
    return list(AMERICAN_SPORTS.keys())

def get_american_sports_slugs() -> List[str]:
    """
    Retorna lista de slugs de esportes americanos para API
    """
    return list(AMERICAN_SPORTS.values())

def get_player_props_for_sport(sport_slug: str) -> List[str]:
    """
    Retorna lista de player props disponíveis para um esporte
    """
    return PLAYER_PROPS_BY_SPORT.get(sport_slug, [])

def is_player_prop_market(market_name: str) -> bool:
    """
    Verifica se um mercado é de player props
    """
    if not market_name:
        return False
    
    market_lower = market_name.lower()
    return any(prop in market_lower for prop in [
        'props', 'player props', 'player', 'points', 'yards', 
        'touchdowns', 'rebounds', 'assists', 'strikeouts',
        'home runs', 'goals', 'shots'
    ])

def get_sport_emoji(sport_name: str) -> str:
    """
    Retorna emoji para um esporte americano
    """
    emoji_map = {
        'NFL': '🏈',
        'College Football': '🏈', 
        'NBA': '🏀',
        'WNBA': '🏀',
        'MLB': '⚾',
        'Minor League Baseball': '⚾',
        'MLS': '⚽',
        'USL Championship': '⚽',
        'NHL': '🏒'
    }
    return emoji_map.get(sport_name, '🏆')

def get_league_region(league_name: str) -> str:
    """
    Retorna região de uma liga americana
    """
    if not league_name:
        return 'Unknown'
    
    if any(league in league_name for league in ['NFL', 'NCAAF', 'NCAA']):
        return 'Football'
    elif any(league in league_name for league in ['NBA', 'WNBA']):
        return 'Basketball'
    elif any(league in league_name for league in ['MLB', 'Minor League']):
        return 'Baseball'
    elif any(league in league_name for league in ['MLS', 'USL', 'NWSL']):
        return 'Soccer'
    elif any(league in league_name for league in ['NHL', 'AHL', 'ECHL']):
        return 'Hockey'
    else:
        return 'Other'

# Configuração do feed americano
FEED_AMERICAN_CONFIG = {
    'feed_id': 'feed_american',
    'name': 'American Sports Feed',
    'description': 'Feed dedicado aos esportes americanos com player props',
    'default_include_props': True,  # Props ativados por padrão
    'max_props_per_game': 5,  # Top 5 props por jogo
    'supported_sports': list(AMERICAN_SPORTS.keys()),
    'setup_steps': 3  # Setup simplificado em 3 passos
}
