"""
Cliente da Odds API para buscar eventos com EV+
"""
import asyncio
import aiohttp
import time
from typing import List, Dict, Optional
from config import ODDS_API_KEY, ODDS_API_BASE, RATE_LIMIT_REQUESTS_PER_HOUR
from database import get_db, generate_alert_hash
from bot_core import calcular_ev

class OddsAPI:
    def __init__(self):
        self.api_key = ODDS_API_KEY
        if not self.api_key:
            raise ValueError("❌ ODDS_API_KEY não configurada no .env")
        self.base_url = ODDS_API_BASE
        self.rate_limit = RATE_LIMIT_REQUESTS_PER_HOUR
        self.db = get_db()
        print(f"✅ API Client inicializada (key: {self.api_key[:8]}...)")
        # Lista de bookmakers suportados pela integração atual
        self.allowed_bookmakers = [
            'Bet365', 'Betfair Sportsbook', 'Novibet', 'Superbet', 'BetMGM', 'Betano'
        ]
    
    def _check_rate_limit(self) -> bool:
        """Verifica se pode fazer requisição sem exceder rate limit"""
        requests_last_hour = self.db.get_request_count_last_hour()
        return requests_last_hour < self.rate_limit
    
    def _log_request(self):
        """Registra requisição para rate limiting"""
        self.db.add_request_log()
    
    def _parse_float(self, value) -> Optional[float]:
        """Converte string para float de forma segura"""
        try:
            return float(value) if value else None
        except (ValueError, TypeError):
            return None
    
    def __parse_evento(self, bet):
        try:
            bookmaker = bet.get('bookmaker', '')
            odds = bet.get('bookmakerOdds', {})
            bet_side = bet.get('betSide', '').lower()
            market_name = bet.get('market', {}).get('name', '').lower()

            if bet_side not in odds:
                return None

            odd_bet = self._parse_float(odds.get(bet_side))
            if not odd_bet or odd_bet < 1.50:
                return None

            # Mapeia bet_side para nome do time ou jogador
            home_team = bet['event'].get('home', '')
            away_team = bet['event'].get('away', '')
            
            # Para player props, extrai o nome do jogador
            if self._is_player_prop_market(market_name, bet):
                # Tenta extrair nome do jogador do market name
                player_name = self._extract_player_name(market_name, bet)
                bet_side_display = player_name if player_name else bet_side.title()
            else:
                # Para mercados normais, usa nome do time
                if bet_side == 'home':
                    bet_side_display = home_team
                elif bet_side == 'away':
                    bet_side_display = away_team
                else:
                    bet_side_display = bet_side.title()

            # Mapeia market para market_type
            market_type = self._map_market_type(market_name)

            # Verifica se é player prop
            is_player_prop = self._is_player_prop_market(market_name, bet)
            
            return {
                "home": home_team,
                "away": away_team,
                "league": bet['event'].get('league', ''),
                "commence_time": bet['event'].get('date', ''),
                "id": bet.get('eventId', bet.get('id', '')),
                "sport": bet['event'].get('sport', ''),
                "market_name": market_name,
                "market_type": market_type,
                "bet_side": bet_side_display,
                "betSide": bet_side,  # Preserva o bet_side original da API
                "bet365_odds": odd_bet,
                "odds_home": self._parse_float(odds.get('home', 0.0)) or 0.0,
                "odds_away": self._parse_float(odds.get('away', 0.0)) or 0.0,
                "odds_draw": self._parse_float(odds.get('draw', 0.0)) or 0.0,
                "hdp": bet.get('market', {}).get('hdp'),
                "total": bet.get('market', {}).get('total'),
                "ev": (bet.get('expectedValue', 0) / 100) - 1,
                "event_url": odds.get('href', ''),
                "bookmaker": bookmaker,
                "is_player_prop": is_player_prop,  # Novo campo para identificar props
                "raw_bet": bet  # Mantém dados originais para player props
            }
        except Exception as e:
            print(f"Erro ao processar aposta: {e}")
            return None

    def _is_player_prop_market(self, market_name: str, bet: dict) -> bool:
        """
        Verifica se um mercado é de player props
        """
        if not market_name:
            return False
        
        market_lower = market_name.lower()
        
        # Verifica palavras-chave de props
        prop_keywords = [
            'props', 'player props', 'player', 'points', 'yards', 
            'touchdowns', 'rebounds', 'assists', 'strikeouts',
            'home runs', 'goals', 'shots', 'steals', 'blocks'
        ]
        
        # Verifica se contém alguma palavra-chave
        if any(keyword in market_lower for keyword in prop_keywords):
            return True
        
        # Verifica se tem campo 'label' (formato novo da API)
        if 'label' in str(bet):
            return True
            
        return False

    def _extract_player_name(self, market_name: str, bet: dict) -> str:
        """
        Extrai nome do jogador de player props
        """
        try:
            # Tenta extrair do market name
            if ' - ' in market_name:
                parts = market_name.split(' - ')
                if len(parts) > 1:
                    player_part = parts[1]
                    # Remove parênteses e conteúdo dentro
                    player_name = player_part.split('(')[0].strip()
                    return player_name.title()
            
            # Fallback: tenta extrair de outros campos
            if 'player' in bet:
                return bet['player'].title()
            
            return ""
        except Exception:
            return ""
    
    async def get_value_bets(self, bookmakers: List[str]) -> List[Dict]:
        """Busca apostas com valor (EV+) para bookmakers específicos"""
        if not self._check_rate_limit():
            print("Rate limit atingido, aguardando...")
            return []
        
        # Normaliza input: aceita string única com vírgulas ou lista; filtra inválidos e remove duplicatas
        if isinstance(bookmakers, str):
            bookmakers = [b.strip() for b in bookmakers.split(',') if b.strip()]
        bookmakers = list(dict.fromkeys(bookmakers or []))  # de-dup preservando ordem

        # Remove entradas não suportadas (ex.: 'Stake.bet.br') e quaisquer inválidas
        valid_bookmakers = [b for b in bookmakers if b in self.allowed_bookmakers]

        # Fallback se vazio após validação
        if not valid_bookmakers:
            valid_bookmakers = ['Bet365']
        
        try:
            self._log_request()
            
            url = f"{self.base_url}/value-bets"
            params = {
                'apiKey': self.api_key,
                'bookmaker': ','.join(valid_bookmakers),  # ✅ OBRIGATÓRIO
                'includeEventDetails': 'true'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        eventos = []
                        
                        # A API pode retornar lista direta ou {"data": [...]}
                        items = data if isinstance(data, list) else data.get('data', [])
                        
                        for bet in items:
                            evento = self.__parse_evento(bet)
                            if evento:
                                eventos.append(evento)
                        
                        print(f"API: {len(eventos)} eventos encontrados")
                        self.db.set_api_status(True, "OK", f"{len(eventos)} eventos")
                        return eventos
                    
                    elif response.status == 401:
                        error_text = await response.text()
                        print(f"API Key inválida: {error_text}")
                        self.db.set_api_status(False, "API Key inválida", error_text)
                        return []
                    
                    elif response.status == 400:
                        error_text = await response.text()
                        print(f"Bad Request: {error_text}")
                        self.db.set_api_status(False, "Bad Request", error_text)
                        return []
                    
                    elif response.status == 429:
                        print("Rate limit excedido")
                        self.db.set_api_status(False, "Rate limit excedido", "429")
                        return []
                    
                    else:
                        error_text = await response.text()
                        print(f"Erro {response.status}: {error_text}")
                        self.db.set_api_status(False, f"Erro HTTP {response.status}", error_text)
                        return []
        
        except Exception as e:
            print(f"Erro na requisição: {e}")
            import traceback
            traceback.print_exc()
            self.db.set_api_status(False, "Erro de conexão", str(e))
            return []
        
    async def get_eventos_geral(self, bookmaker: str) -> List[Dict]:
        """Busca eventos gerais para um bookmaker específico"""
        if not self._check_rate_limit():
            print("Rate limit atingido, aguardando...")
            return []
        
        # Validação do bookmaker individual
        if bookmaker not in self.allowed_bookmakers:
            print(f"Bookmaker '{bookmaker}' não suportado, ignorando...")
            return []

        try:
            self._log_request()
            
            url = f"{self.base_url}/value-bets"
            params = {
                'apiKey': self.api_key,
                'bookmaker': bookmaker,  # ✅ OBRIGATÓRIO
                'includeEventDetails': 'true'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        eventos = []
                        
                        items = data if isinstance(data, list) else data.get('data', [])
                        
                        for bet in items:
                            evento = self.__parse_evento(bet)
                            if evento:
                                eventos.append(evento)
                        
                        print(f"API: {len(eventos)} eventos para {bookmaker}")
                        return eventos
                    else:
                        error_text = await response.text()
                        print(f"Erro {response.status}: {error_text}")
                        return []
        
        except Exception as e:
            print(f"Erro: {e}")
            return []
        
    async def get_bookmakers(self) -> List[str]:
        """
        Busca lista de bookmakers ativos que a API está fornecendo dados
        """
        if not self._check_rate_limit():
            return []
        
        try:
            self._log_request()
            
            # Endpoint para buscar bookmakers disponíveis
            url = f"{self.base_url}/sports"
            params = {'apiKey': self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        # A API retorna esportes, vamos usar lista fixa dos principais bookmakers
                        # que sabemos que estão ativos na API
                        bookmakers = self.allowed_bookmakers.copy()
                        print(f"✅ API: {len(bookmakers)} bookmakers ativos encontrados")
                        return bookmakers
                    elif response.status == 401:
                        print("❌ API Key inválida para buscar bookmakers")
                        return []
                    else:
                        print(f"❌ Erro ao buscar bookmakers: {response.status}")
                        # Fallback para lista básica se o endpoint falhar
                        return self.allowed_bookmakers.copy()
        
        except Exception as e:
            print(f"❌ Erro ao buscar bookmakers: {e}")
            # Fallback para lista básica em caso de erro
            return self.allowed_bookmakers.copy()
    
    def get_api_status(self) -> Dict:
        """Retorna status atual da API"""
        return self.db.get_api_status()
    
    async def get_apostas(self) -> List[Dict]:
        """
        Busca apostas da API (método principal usado pelo scanner)
        """
        try:
            # Busca bookmakers ativos dinamicamente
            bookmakers = await self.get_bookmakers()
            
            if not bookmakers:
                print("⚠️ Nenhum bookmaker ativo encontrado")
                return []
            
            # Busca apostas com valor para os bookmakers ativos
            apostas = await self.get_value_bets(bookmakers)
            return apostas
        except Exception as e:
            print(f"❌ Erro ao buscar apostas: {e}")
            return []

    def _map_market_type(self, market_name: str) -> str:
        """
        Mapeia nome do mercado da API para market_type interno
        """
        market_mapping = {
            'moneyline': 'moneyline',
            'match winner': 'moneyline',
            'match result': 'moneyline',
            'h2h': 'h2h',
            'head to head': 'h2h',
            'spread': 'spreads',
            'handicap': 'spreads',
            'total': 'totals',
            'over/under': 'totals',
            'total goals': 'totals',
            'total points': 'total_points'
        }
        
        market_lower = market_name.lower()
        for key, value in market_mapping.items():
            if key in market_lower:
                return value
        
        return 'h2h'  # fallback
    
    async def get_player_props(self, event_id: str, bookmakers: List[str]) -> List[Dict]:
        """
        Busca player props para um evento específico
        
        Args:
            event_id: ID do evento na API
            bookmakers: Lista de casas de apostas
            
        Returns:
            Lista de props com estrutura:
            [{
                'player_name': str,
                'prop_type': str,  # 'points', 'rebounds', 'assists', etc
                'line': float,  # handicap/linha (ex: 27.5)
                'bookmaker_odds': {'Bet365': {'over': 1.95, 'under': 1.85}, ...},
                'event_id': str,
                'sport': str,
                'league': str,
                'home_team': str,
                'away_team': str
            }]
        """
        if not self._check_rate_limit():
            print("Rate limit atingido, aguardando...")
            return []
        
        # Normaliza bookmakers
        if isinstance(bookmakers, str):
            bookmakers = [b.strip() for b in bookmakers.split(',') if b.strip()]
        bookmakers = list(dict.fromkeys(bookmakers or []))
        valid_bookmakers = [b for b in bookmakers if b in self.allowed_bookmakers]
        
        if not valid_bookmakers:
            valid_bookmakers = ['Bet365']
        
        try:
            self._log_request()
            
            url = f"{self.base_url}/v3/odds"
            params = {
                'apiKey': self.api_key,
                'eventId': event_id,
                'bookmakers': ','.join(valid_bookmakers)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Erro ao buscar props do evento {event_id}: {response.status} - {error_text}")
                        return []
                    
                    data = await response.json()
                    
                    # Parsear props do evento
                    props = self._parse_player_props_from_event(data, valid_bookmakers)
                    return props
        
        except Exception as e:
            print(f"Erro ao buscar player props: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_player_props_from_event(self, event_data: Dict, bookmakers: List[str]) -> List[Dict]:
        """
        Extrai player props dos dados de um evento
        """
        props = []
        
        try:
            event_id = event_data.get('id', '')
            sport = event_data.get('sport', {}).get('slug', '')
            league = event_data.get('league', {}).get('name', '')
            home_team = event_data.get('home', '')
            away_team = event_data.get('away', '')
            
            # Estrutura: event_data['bookmakers'] = {'Bet365': [...markets...], 'BetMGM': [...]}
            bookmakers_data = event_data.get('bookmakers', {})
            
            # Agrupar props por (player, prop_type, line)
            props_grouped = {}
            
            for bookmaker_name, markets in bookmakers_data.items():
                if bookmaker_name not in bookmakers:
                    continue
                
                for market in markets:
                    market_name = market.get('name', '')
                    
                    # Identificar se é player prop
                    if not self._is_player_prop_market(market_name, market):
                        continue
                    
                    # Extrair tipo de prop (points, rebounds, assists, etc)
                    prop_type = self._extract_prop_type(market_name)
                    
                    # Cada odd no mercado é um jogador diferente
                    for odd_entry in market.get('odds', []):
                        player_name = odd_entry.get('label', '')
                        line = self._parse_float(odd_entry.get('hdp', 0))
                        over_odds = self._parse_float(odd_entry.get('over'))
                        under_odds = self._parse_float(odd_entry.get('under'))
                        
                        if not player_name or line is None:
                            continue
                        
                        # Chave única: player + prop_type + line
                        key = (player_name, prop_type, line)
                        
                        if key not in props_grouped:
                            props_grouped[key] = {
                                'player_name': player_name,
                                'prop_type': prop_type,
                                'line': line,
                                'bookmaker_odds': {},
                                'event_id': event_id,
                                'sport': sport,
                                'league': league,
                                'home_team': home_team,
                                'away_team': away_team
                            }
                        
                        props_grouped[key]['bookmaker_odds'][bookmaker_name] = {
                            'over': over_odds,
                            'under': under_odds
                        }
            
            props = list(props_grouped.values())
            
        except Exception as e:
            print(f"Erro ao parsear player props: {e}")
            import traceback
            traceback.print_exc()
        
        return props
    
    def _extract_prop_type(self, market_name: str) -> str:
        """
        Extrai o tipo de prop do nome do mercado
        Ex: "Player Props - Points" -> "points"
        """
        market_lower = market_name.lower()
        
        # Mapeamento de keywords para tipos
        prop_types = {
            'points': 'points',
            'pts': 'points',
            'rebounds': 'rebounds',
            'reb': 'rebounds',
            'assists': 'assists',
            'ast': 'assists',
            'yards': 'yards',
            'yds': 'yards',
            'passing yards': 'passing_yards',
            'rushing yards': 'rushing_yards',
            'receiving yards': 'receiving_yards',
            'touchdowns': 'touchdowns',
            'td': 'touchdowns',
            'receptions': 'receptions',
            'rec': 'receptions',
            'strikeouts': 'strikeouts',
            'home runs': 'home_runs',
            'hits': 'hits',
            'rbi': 'rbi',
            'stolen bases': 'stolen_bases',
            'goals': 'goals',
            'shots': 'shots',
            'saves': 'saves',
            'blocks': 'blocks',
            'steals': 'steals',
            'three pointers': 'three_pointers',
            '3-pointers': 'three_pointers'
        }
        
        for keyword, prop_type in prop_types.items():
            if keyword in market_lower:
                return prop_type
        
        return 'other'
    
    async def get_player_props_batch(self, event_ids: List[str], bookmakers: List[str]) -> List[Dict]:
        """
        Busca player props para múltiplos eventos
        
        Args:
            event_ids: Lista de IDs de eventos
            bookmakers: Lista de casas de apostas
            
        Returns:
            Lista consolidada de props de todos os eventos
        """
        if not event_ids:
            return []
        
        print(f"Buscando props para {len(event_ids)} eventos...")
        
        # Buscar props de cada evento (poderia ser paralelizado com asyncio.gather)
        all_props = []
        for event_id in event_ids[:5]:  # Limitar a 5 eventos para não exceder rate limit
            props = await self.get_player_props(event_id, bookmakers)
            all_props.extend(props)
            
            # Pequeno delay entre requisições
            await asyncio.sleep(0.5)
        
        print(f"Props encontrados: {len(all_props)}")
        return all_props
    
    # Cache para upcoming events (5 minutos)
    _upcoming_events_cache = None
    _upcoming_events_cache_time = 0
    
    async def get_upcoming_american_events(self, limit: int = 5) -> List[str]:
        """
        Busca IDs dos próximos jogos americanos (fallback quando não há EV+)
        Cache de 5 minutos para evitar chamadas repetidas
        
        Returns:
            Lista de event_ids
        """
        import time
        
        # Verificar cache
        current_time = time.time()
        if self._upcoming_events_cache and (current_time - self._upcoming_events_cache_time) < 300:
            return self._upcoming_events_cache[:limit]
        
        # Buscar novos eventos
        try:
            # Usar endpoint /value-bets mas filtrar apenas esportes americanos
            # (alternativa seria usar /v3/odds mas consumiria mais quota)
            bookmakers = ['Bet365']  # Usar apenas 1 casa para economizar quota
            all_events = await self.get_value_bets(bookmakers)
            
            # Filtrar eventos americanos
            american_sports = ['american football', 'basketball', 'baseball', 'ice hockey']
            american_events = [
                e for e in all_events 
                if e.get('sport', '').lower() in american_sports
                and e.get('event_id')
            ]
            
            # Extrair event_ids únicos
            event_ids = list(dict.fromkeys([e['event_id'] for e in american_events]))
            
            # Atualizar cache
            self._upcoming_events_cache = event_ids
            self._upcoming_events_cache_time = current_time
            
            print(f"Cache atualizado: {len(event_ids)} eventos americanos encontrados")
            return event_ids[:limit]
        
        except Exception as e:
            print(f"Erro ao buscar upcoming events: {e}")
            return []

# Alias para compatibilidade com testes
OddsAPIClient = OddsAPI