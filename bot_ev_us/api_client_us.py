"""
Cliente da Odds API para feed americano - versão otimizada para US sports
"""
import asyncio
import aiohttp
import time
import logging
from typing import List, Dict, Optional, AsyncGenerator, Union
from config import ODDS_API_KEY, ODDS_API_BASE, RATE_LIMIT_REQUESTS_PER_HOUR
from database import get_db

class OddsApiUSClient:
    def __init__(self):
        self.api_key = ODDS_API_KEY
        if not self.api_key:
            raise ValueError("ODDS_API_KEY não configurada no .env")
        self.base_url = ODDS_API_BASE
        self.rate_limit = RATE_LIMIT_REQUESTS_PER_HOUR
        self.db = get_db()
        self.logger = logging.getLogger(__name__)
        
        # Configurações de resiliência
        self.timeout = aiohttp.ClientTimeout(total=20)
        self.max_retries = 2
        self.backoff_delays = [1, 3]  # segundos
        
        print(f"US API Client inicializada (key: {self.api_key[:8]}...)")
    
    def _check_rate_limit(self) -> bool:
        """Verifica se pode fazer requisição sem exceder rate limit"""
        requests_last_hour = self.db.get_request_count_last_hour()
        return requests_last_hour < self.rate_limit
    
    def _log_request(self):
        """Registra requisição para rate limiting"""
        self.db.add_request_log()
    
    async def _make_request_with_retry(self, url: str, params: dict, method: str = "GET") -> Optional[dict]:
        """
        Faz requisição com retry e backoff
        """
        if not self._check_rate_limit():
            self.logger.warning("Rate limit atingido, aguardando...")
            return None
        
        for attempt in range(self.max_retries + 1):
            try:
                self._log_request()
                
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    if method.upper() == "GET":
                        async with session.get(url, params=params) as response:
                            return await self._handle_response(response, url, params)
                    else:
                        async with session.post(url, json=params) as response:
                            return await self._handle_response(response, url, params)
                            
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout na tentativa {attempt + 1} para {url}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_delays[attempt])
                    continue
                return None
                
            except Exception as e:
                self.logger.error(f"Erro na tentativa {attempt + 1} para {url}: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff_delays[attempt])
                    continue
                return None
        
        return None
    
    async def _handle_response(self, response: aiohttp.ClientResponse, url: str, params: dict) -> Optional[dict]:
        """Handle HTTP response with proper error handling"""
        if response.status == 200:
            data = await response.json()
            # Log apenas tamanho e IDs, nunca payload
            if isinstance(data, list):
                self.logger.info(f"{url}: {len(data)} itens retornados")
            elif isinstance(data, dict):
                self.logger.info(f"{url}: resposta dict recebida")
            return data
            
        elif response.status == 401:
            self.logger.error("API Key inválida")
            return None
            
        elif response.status == 429:
            self.logger.warning("Rate limit excedido")
            return None
            
        elif response.status >= 500:
            self.logger.warning(f"Erro servidor {response.status}")
            return None
            
        else:
            error_text = await response.text()
            self.logger.error(f"Erro {response.status}: {error_text[:100]}...")
            return None
    
    async def get_events_paginated(self, sport_slug: str, league_slug: str, status: str = "pending", limit: int = 100) -> AsyncGenerator[Dict, None]:
        """
        Generator/async iterator que pagina o endpoint /v3/events
        Filtra localmente data futura (UTC) e respeita rate limit
        """
        page = 1
        per_page = min(limit, 100)  # Máximo da API
        
        while True:
            url = f"{self.base_url}/events"
            params = {
                'apiKey': self.api_key,
                'sport': sport_slug,
                'league': league_slug,
                'status': status,
                'page': page,
                'perPage': per_page
            }
            
            data = await self._make_request_with_retry(url, params)
            if not data:
                break
            
            # Se não é lista, pode ser dict com 'data' ou 'events'
            events = data
            if isinstance(data, dict):
                events = data.get('data', data.get('events', []))
            
            if not isinstance(events, list):
                self.logger.warning(f"Formato inesperado de resposta: {type(events)}")
                break
            
            # Filtra eventos futuros (UTC)
            current_time = time.time()
            future_events = []
            
            for event in events:
                try:
                    # Assumindo que o campo de data é 'commenceTime' ou 'date'
                    event_time_str = event.get('commenceTime') or event.get('date', '')
                    if event_time_str:
                        # Converte para timestamp se necessário
                        if isinstance(event_time_str, str):
                            from datetime import datetime
                            event_dt = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
                            event_timestamp = event_dt.timestamp()
                        else:
                            event_timestamp = float(event_time_str)
                        
                        # Só inclui eventos futuros
                        if event_timestamp > current_time:
                            future_events.append(event)
                except Exception as e:
                    self.logger.debug(f"Erro ao processar data do evento: {e}")
                    continue
            
            if not future_events:
                self.logger.info(f"Nenhum evento futuro encontrado na página {page}")
                break
            
            # Yield eventos da página atual
            for event in future_events:
                yield event
            
            # Se retornou menos que o esperado, é a última página
            if len(events) < per_page:
                break
            
            page += 1
            
            # Rate limiting: pequena pausa entre páginas
            await asyncio.sleep(0.1)
    
    async def get_event_odds(self, event_id: int, bookmakers_csv: str) -> dict:
        """
        Busca odds de um evento específico
        """
        url = f"{self.base_url}/odds"
        params = {
            'apiKey': self.api_key,
            'eventId': str(event_id),
            'bookmakers': bookmakers_csv
        }
        
        data = await self._make_request_with_retry(url, params)
        if data:
            self.logger.info(f"✅ Odds para evento {event_id}: {len(data.get('bookmakers', {}))} bookmakers")
        
        return data or {}
    
    async def get_odds_multiple(self, event_ids: List[int], bookmakers_csv: str, chunk_size: int = 10) -> List[dict]:
        """
        Busca odds para múltiplos eventos usando /v3/odds/multi
        Processa em chunks de até 10 IDs
        """
        all_results = []
        
        # Processa em chunks
        for i in range(0, len(event_ids), chunk_size):
            chunk = event_ids[i:i + chunk_size]
            
            url = f"{self.base_url}/odds/multi"
            params = {
                'apiKey': self.api_key,
                'eventIds': ','.join(map(str, chunk)),
                'bookmakers': bookmakers_csv
            }
            
            data = await self._make_request_with_retry(url, params)
            if data:
                if isinstance(data, list):
                    all_results.extend(data)
                    self.logger.info(f"✅ Chunk {i//chunk_size + 1}: {len(data)} eventos processados")
                else:
                    self.logger.warning(f"Formato inesperado no chunk {i//chunk_size + 1}: {type(data)}")
            
            # Pequena pausa entre chunks
            if i + chunk_size < len(event_ids):
                await asyncio.sleep(0.2)
        
        self.logger.info(f"✅ Total: {len(all_results)} eventos processados")
        return all_results
    
    async def search_events(self, query: str) -> List[dict]:
        """
        Busca eventos por query de texto
        """
        url = f"{self.base_url}/events/search"
        params = {
            'apiKey': self.api_key,
            'query': query
        }
        
        data = await self._make_request_with_retry(url, params)
        if data:
            events = data if isinstance(data, list) else data.get('data', [])
            self.logger.info(f"✅ Busca '{query}': {len(events)} eventos encontrados")
            return events
        
        return []
    
    def get_api_status(self) -> Dict:
        """Retorna status atual da API"""
        return self.db.get_api_status()
    
    async def test_connection(self) -> bool:
        """
        Testa conexão com a API
        """
        try:
            url = f"{self.base_url}/sports"
            params = {'apiKey': self.api_key}
            
            data = await self._make_request_with_retry(url, params)
            if data:
                self.logger.info("Conexão com API OK")
                return True
            else:
                self.logger.error("Falha na conexão com API")
                return False
        except Exception as e:
            self.logger.error(f"Erro no teste de conexão: {e}")
            return False
