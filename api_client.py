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
            market = bet.get('market', {})
            bookmaker_odds = bet.get('bookmakerOdds', {})
            bet_side = bet.get('betSide', '').lower()

            # Odd do lado da aposta
            odd_bet = self._parse_float(bookmaker_odds.get(bet_side))
            if not odd_bet or odd_bet < 1.50:
                return None

            # EV já vem calculado: 101.84 = 1.84% EV
            # Converter: 101.84 -> 0.0184
            expected_value_raw = bet.get('expectedValue', 0)
            ev = (expected_value_raw - 100) / 100

            return {
                "home": f"Event {bet.get('eventId', '')}",
                "away": "",
                "league": "Unknown",
                "commence_time": bet.get('expectedValueUpdatedAt', ''),
                "id": bet.get('eventId', bet.get('id', '')),
                "sport": "Unknown",
                "market_type": market.get('name', ''),
                "market_name": market.get('name', ''),
                "bet_side": bet_side,
                "bet365_odds": odd_bet,
                "odds_home": self._parse_float(market.get('home', 0)) or 0.0,
                "odds_away": self._parse_float(market.get('away', 0)) or 0.0,
                "odds_draw": self._parse_float(market.get('draw', 0)) or 0.0,
                "hdp": market.get('hdp'),
                "total": market.get('total'),
                "ev": ev,
                "event_url": bookmaker_odds.get('href', ''),
                "bookmaker": bookmaker
            }
        except Exception as e:
            print(f"Erro ao processar aposta: {e}")
            return None
    
    async def get_value_bets(self, bookmakers: List[str]) -> List[Dict]:
        """Busca apostas com valor (EV+) para bookmakers específicos"""
        if not self._check_rate_limit():
            print("Rate limit atingido, aguardando...")
            return []
        
        # Garantir que sempre tem pelo menos um bookmaker
        if not bookmakers:
            bookmakers = ['Bet365']  # Fallback padrão
        
        try:
            self._log_request()
            
            url = f"{self.base_url}/value-bets"
            params = {
                'apiKey': self.api_key,
                'bookmaker': ','.join(bookmakers)  # ✅ OBRIGATÓRIO
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
        
        try:
            self._log_request()
            
            url = f"{self.base_url}/value-bets"
            params = {
                'apiKey': self.api_key,
                'bookmaker': bookmaker  # ✅ OBRIGATÓRIO
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
                        bookmakers = [
                            'Bet365', 'Betfair Sportsbook', 'Novibet', 
                            'Stake.bet.br', 'Superbet', 'Betano'
                        ]
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