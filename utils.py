"""
Utilitários gerais do bot
"""
import logging
import pycountry
from typing import Dict, List, Optional, Any
from database import get_db

# Configuração de logging
def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Configura logger para um módulo"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# Loggers globais
logger_geral = setup_logger("bot_geral")
logger_scan = setup_logger("bot_scan")
logger_alertas = setup_logger("bot_alertas")

# Catálogo de ligas por região
LIGAS_POR_REGIAO = {
    "Brasil": {
        "Football": [
            "Brazil - Serie A",
            "Brazil - Serie B", 
            "Brazil - Copa do Brasil",
            "Brazil - Campeonato Carioca",
            "Brazil - Campeonato Paulista",
            "Brazil - Campeonato Mineiro",
            "Brazil - Campeonato Gaúcho"
        ],
        "Basketball": [
            "Brazil - NBB",
            "Brazil - Liga Ouro"
        ],
        "Tennis": [
            "Brazil - ATP Challenger"
        ]
    },
    "Europa": {
        "Football": [
            "England - Premier League",
            "England - Championship",
            "Spain - La Liga",
            "Spain - Segunda División",
            "Germany - Bundesliga",
            "Germany - 2. Bundesliga",
            "Italy - Serie A",
            "Italy - Serie B",
            "France - Ligue 1",
            "France - Ligue 2",
            "Portugal - Primeira Liga",
            "Netherlands - Eredivisie",
            "Belgium - Pro League",
            "Turkey - Süper Lig",
            "Russia - Premier League",
            "Ukraine - Premier League",
            "Poland - Ekstraklasa",
            "Czech Republic - First League",
            "Austria - Bundesliga",
            "Switzerland - Super League",
            "Scotland - Premiership",
            "Norway - Eliteserien",
            "Sweden - Allsvenskan",
            "Denmark - Superliga",
            "Greece - Super League",
            "Croatia - HNL",
            "Serbia - SuperLiga",
            "Romania - Liga I",
            "Bulgaria - First League",
            "Hungary - NB I",
            "Slovakia - Super Liga",
            "Slovenia - PrvaLiga",
            "International Clubs - UEFA Champions League",
            "International Clubs - UEFA Europa League",
            "International Clubs - UEFA Europa Conference League",
            "International - UEFA Nations League",
            "International - European Championship",
            "International - World Cup"
        ],
        "Basketball": [
            "Spain - ACB",
            "Germany - BBL",
            "France - Pro A",
            "Italy - Serie A",
            "Turkey - BSL",
            "Greece - A1",
            "Russia - VTB United League",
            "International Clubs - EuroLeague",
            "International Clubs - EuroCup"
        ],
        "Tennis": [
            "ATP - Masters 1000",
            "ATP - 500",
            "ATP - 250",
            "WTA - 1000",
            "WTA - 500",
            "WTA - 250",
            "International - Grand Slam"
        ]
    },
    "América do Sul": {
        "Football": [
            "Argentina - Primera División",
            "Argentina - Primera B Nacional",
            "Chile - Primera División",
            "Colombia - Primera A",
            "Peru - Liga 1",
            "Uruguay - Primera División",
            "Paraguay - Primera División",
            "Bolivia - Primera División",
            "Ecuador - Serie A",
            "Venezuela - Primera División",
            "International - Copa Libertadores",
            "International - Copa Sudamericana",
            "International - Copa América"
        ],
        "Basketball": [
            "Argentina - Liga Nacional",
            "Chile - Liga Nacional"
        ]
    },
    "América do Norte": {
        "Football": [
            "USA - MLS",
            "USA - USL Championship",
            "Mexico - Liga MX",
            "Canada - CPL",
            "International - CONCACAF Champions League"
        ],
        "Basketball": [
            "USA - NBA",
            "USA - NCAA",
            "Canada - CEBL"
        ],
        "Baseball": [
            "USA - MLB",
            "USA - NCAA Baseball"
        ],
        "Ice Hockey": [
            "USA - NHL",
            "USA - NCAA Hockey"
        ]
    },
    "Ásia": {
        "Football": [
            "Japan - J1 League",
            "South Korea - K League 1",
            "China - Super League",
            "Australia - A-League",
            "Saudi Arabia - Pro League",
            "UAE - Pro League",
            "Qatar - Stars League",
            "Thailand - Thai League 1",
            "Vietnam - V.League 1",
            "International - AFC Champions League"
        ],
        "Basketball": [
            "China - CBA",
            "Japan - B.League",
            "Australia - NBL"
        ]
    }
}

def get_league_catalog() -> Dict[str, Dict[str, List[str]]]:
    """Retorna catálogo de ligas do banco ou padrão"""
    db = get_db()
    catalog = db.get_league_catalog()
    
    # Se não há dados no banco, retorna catálogo padrão
    if not catalog:
        return LIGAS_POR_REGIAO
    
    return catalog

def update_league_catalog(catalog: Dict[str, Dict[str, List[str]]]):
    """Atualiza catálogo de ligas no banco"""
    db = get_db()
    db.update_league_catalog(catalog)

def get_country_flag(country_name: str) -> str:
    """Retorna emoji da bandeira de um país"""
    try:
        # Mapeamento manual para casos especiais
        country_mapping = {
            "Brazil": "BR",
            "England": "GB",
            "Spain": "ES", 
            "Germany": "DE",
            "Italy": "IT",
            "France": "FR",
            "Portugal": "PT",
            "Netherlands": "NL",
            "Belgium": "BE",
            "Turkey": "TR",
            "Russia": "RU",
            "Ukraine": "UA",
            "Poland": "PL",
            "Czech Republic": "CZ",
            "Austria": "AT",
            "Switzerland": "CH",
            "Scotland": "GB",
            "Norway": "NO",
            "Sweden": "SE",
            "Denmark": "DK",
            "Greece": "GR",
            "Croatia": "HR",
            "Serbia": "RS",
            "Romania": "RO",
            "Bulgaria": "BG",
            "Hungary": "HU",
            "Slovakia": "SK",
            "Slovenia": "SI",
            "Argentina": "AR",
            "Chile": "CL",
            "Colombia": "CO",
            "Peru": "PE",
            "Uruguay": "UY",
            "Paraguay": "PY",
            "Bolivia": "BO",
            "Ecuador": "EC",
            "Venezuela": "VE",
            "USA": "US",
            "Mexico": "MX",
            "Canada": "CA",
            "Japan": "JP",
            "South Korea": "KR",
            "China": "CN",
            "Australia": "AU",
            "Saudi Arabia": "SA",
            "UAE": "AE",
            "Qatar": "QA",
            "Thailand": "TH",
            "Vietnam": "VN"
        }
        
        country_code = country_mapping.get(country_name)
        if country_code:
            country = pycountry.countries.get(alpha_2=country_code)
            if country:
                # Converte código do país para emoji da bandeira
                return ''.join(chr(ord(c) + 127397) for c in country.alpha_2)
        
        return "🏳️"
    
    except Exception:
        return "🏳️"

def format_league_name(league: str) -> str:
    """Formata nome da liga com bandeira do país"""
    if " - " in league:
        country, league_name = league.split(" - ", 1)
        flag = get_country_flag(country)
        return f"{flag} {league}"
    return league

def get_sports_list() -> List[str]:
    """Retorna lista de esportes disponíveis"""
    return ["Football", "Basketball", "Tennis", "Baseball", "Ice Hockey"]

def get_regions_list() -> List[str]:
    """Retorna lista de regiões disponíveis"""
    return list(LIGAS_POR_REGIAO.keys())

def get_leagues_by_region_sport(region: str, sport: str) -> List[str]:
    """Retorna ligas de uma região e esporte específicos"""
    catalog = get_league_catalog()
    return catalog.get(region, {}).get(sport, [])

def is_valid_league(league: str) -> bool:
    """Verifica se uma liga é válida"""
    catalog = get_league_catalog()
    for region_data in catalog.values():
        for leagues in region_data.values():
            if league in leagues:
                return True
    return False

def is_valid_sport(sport: str) -> bool:
    """Verifica se um esporte é válido"""
    return sport in get_sports_list()

def is_valid_region(region: str) -> bool:
    """Verifica se uma região é válida"""
    return region in get_regions_list()

async def carregar_catalogo_ligas() -> Dict[str, Any]:
    """Carrega catálogo de ligas do banco de dados (versão async)"""
    try:
        from database import SQLiteConnectionPool, SQLiteConnectionConfig
        import os
        
        db_config = SQLiteConnectionConfig(
            database_path=os.path.join(os.getcwd(), "data", "bot.db"),
            max_connections=10,
            timeout=30.0
        )
        db_pool = SQLiteConnectionPool(db_config)
        
        async with db_pool.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM league_catalog")
            ligas = {}
            for row in await cursor.fetchall():
                ligas[row['league_name']] = {
                    'sport': row['sport'],
                    'region': row['region'],
                    'country': row['country']
                }
            return ligas
            
    except Exception as e:
        logger_geral.error(f"Erro ao carregar catálogo de ligas: {e}")
        return {}

# Tradução de esportes para inglês (usado na API)
TRADUCAO_ESPORTE_EN = {
    "Futebol": "soccer",
    "Basquete": "basketball", 
    "Tênis": "tennis",
    "Vôlei": "volleyball",
    "Handebol": "handball",
    "Futebol Americano": "americanfootball",
    "Baseball": "baseball",
    "Hockey": "icehockey",
    "Cricket": "cricket",
    "Rugby": "rugby"
}
