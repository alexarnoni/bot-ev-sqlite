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
        self.base_url = ODDS_API_BASE
        self.rate_limit = RATE_LIMIT_REQUESTS_PER_HOUR
        self.db = get_db()
    
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
        """Parse de um evento da API para formato interno"""
        try:
            bookmaker = bet.get('bookmaker', '')
            odds = bet.get('bookmakerOdds', {})
            bet_side = bet.get('betSide', '').lower()

            if bet_side not in odds:
                return None

            odd_bet = self._parse_float(odds.get(bet_side))
            if not odd_bet or odd_bet < 1.50:
                return None

            # API já retorna EV calculado
            expected_value_raw = bet.get('expectedValue', 0)
            # Converte para formato interno: 100.84 → 0.0084
            ev = calcular_ev(bet)

            return {
                "home": bet['event'].get('home', ''),
                "away": bet['event'].get('away', ''),
                "league": bet['event'].get('league', ''),
                "commence_time": bet['event'].get('date', ''),
                "id": bet.get('eventId', bet.get('id', '')),
                "sport": bet['event'].get('sport', ''),
                "market_type": bet.get('market', {}).get('name', bet.get('market_type', '')),
                "market_name": bet.get('market', {}).get('name', ''),
                "bet_side": bet.get('betSide', ''),
                "bet365_odds": odd_bet,
                "odds_home": self._parse_float(odds.get('home', 0.0)) or 0.0,
                "odds_away": self._parse_float(odds.get('away', 0.0)) or 0.0,
                "odds_draw": self._parse_float(odds.get('draw', 0.0)) or 0.0,
                "hdp": bet.get('market', {}).get('hdp'),
                "total": bet.get('market', {}).get('total'),
                "ev": ev,  # JÁ CONVERTIDO
                "event_url": odds.get('href', ''),
                "bookmaker": bookmaker
            }
        except Exception as e:
            print(f"Erro ao processar aposta: {e}")
            return None
    
    async def get_value_bets(self, bookmakers: List[str]) -> List[Dict]:
        """
        Busca apostas com valor (EV+) para bookmakers específicos
        """
        if not self._check_rate_limit():
            print("⚠️ Rate limit atingido, aguardando...")
            return []
        
        try:
            self._log_request()
            
            # Converte lista de bookmakers para string da API
            bookmakers_str = ','.join(bookmakers)
            
            url = f"{self.base_url}/sports/all/odds"
            params = {
                'apiKey': self.api_key,
                'regions': 'us',
                'markets': 'h2h,spreads,totals',
                'bookmakers': bookmakers_str,
                'oddsFormat': 'decimal'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        eventos = []
                        
                        for bet in data:
                            evento = self.__parse_evento(bet)
                            if evento:
                                eventos.append(evento)
                        
                        print(f"✅ API: {len(eventos)} eventos encontrados para {len(bookmakers)} bookmakers")
                        return eventos
                    
                    elif response.status == 401:
                        print("❌ API Key inválida")
                        self.db.set_api_status(False, "API Key inválida", f"Status: {response.status}")
                        return []
                    
                    elif response.status == 429:
                        print("❌ Rate limit excedido")
                        self.db.set_api_status(False, "Rate limit excedido", f"Status: {response.status}")
                        return []
                    
                    else:
                        print(f"❌ Erro na API: {response.status}")
                        self.db.set_api_status(False, f"Erro HTTP {response.status}", await response.text())
                        return []
        
        except Exception as e:
            print(f"❌ Erro na requisição: {e}")
            self.db.set_api_status(False, "Erro de conexão", str(e))
            return []
    
    async def get_eventos_geral(self, bookmaker: str) -> List[Dict]:
        """
        Busca eventos gerais para um bookmaker específico
        """
        if not self._check_rate_limit():
            print("⚠️ Rate limit atingido, aguardando...")
            return []
        
        try:
            self._log_request()
            
            url = f"{self.base_url}/sports/all/odds"
            params = {
                'apiKey': self.api_key,
                'regions': 'us',
                'markets': 'h2h,spreads,totals',
                'bookmakers': bookmaker,
                'oddsFormat': 'decimal'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        eventos = []
                        
                        for bet in data:
                            evento = self.__parse_evento(bet)
                            if evento:
                                eventos.append(evento)
                        
                        print(f"✅ API: {len(eventos)} eventos para {bookmaker}")
                        return eventos
                    
                    else:
                        print(f"❌ Erro na API para {bookmaker}: {response.status}")
                        return []
        
        except Exception as e:
            print(f"❌ Erro na requisição para {bookmaker}: {e}")
            return []
    
    async def get_bookmakers(self) -> List[str]:
        """
        Busca lista de bookmakers ativos que a API está fornecendo dados
        """
        if not self._check_rate_limit():
            return []
        
        try:
            self._log_request()
            
            # Endpoint específico para bookmakers selecionados/ativos
            url = f"{self.base_url}/bookmakers/selected"
            params = {'apiKey': self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        bookmakers = data.get('bookmakers', [])
                        print(f"✅ API: {len(bookmakers)} bookmakers ativos encontrados")
                        return bookmakers
                    elif response.status == 401:
                        print("❌ API Key inválida para buscar bookmakers")
                        return []
                    else:
                        print(f"❌ Erro ao buscar bookmakers: {response.status}")
                        # Fallback para lista básica se o endpoint falhar
                        return [
                            'Bet365', 'Betfair Sportsbook', 'Novibet', 
                            'Stake.bet.br', 'Superbet', 'Betano'
                        ]
        
        except Exception as e:
            print(f"❌ Erro ao buscar bookmakers: {e}")
            # Fallback para lista básica em caso de erro
            return [
                'Bet365', 'Betfair Sportsbook', 'Novibet', 
                'Stake.bet.br', 'Superbet', 'Betano'
            ]
    
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

# Alias para compatibilidade com testes
OddsAPIClient = OddsAPI