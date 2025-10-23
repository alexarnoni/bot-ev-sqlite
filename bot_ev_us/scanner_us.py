"""
Scanner para feed americano - descobre eventos e gerencia cache
"""
import asyncio
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from database import get_db
from bot_ev_us.api_client_us import OddsApiUSClient

class USEventScanner:
    def __init__(self):
        self.db = get_db()
        self.api_client = OddsApiUSClient()
        self.logger = logging.getLogger(__name__)
        
        # Configurações do ENV
        self.usa_sports = os.getenv("USA_SPORTS", "basketball,american-football,baseball,ice-hockey").split(",")
        self.usa_leagues = os.getenv("USA_LEAGUES", "usa-nba,usa-nfl,usa-mlb,usa-nhl").split(",")
        
        # Limpa espaços em branco
        self.usa_sports = [s.strip() for s in self.usa_sports if s.strip()]
        self.usa_leagues = [l.strip() for l in self.usa_leagues if l.strip()]
        
        self.logger.info(f"✅ US Scanner inicializado - Sports: {self.usa_sports}, Leagues: {self.usa_leagues}")
    
    def _ensure_events_cache_table(self):
        """
        Cria tabela events_cache se não existir
        """
        try:
            # Verifica se tabela existe
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='events_cache'
            """)
            
            if not cursor.fetchone():
                # Cria tabela se não existir
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS events_cache (
                        id INTEGER PRIMARY KEY,
                        sport TEXT NOT NULL,
                        league TEXT NOT NULL,
                        home TEXT NOT NULL,
                        away TEXT NOT NULL,
                        date_utc TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Cria índices para performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_cache_sport_league ON events_cache(sport, league)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_cache_date ON events_cache(date_utc)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_cache_status ON events_cache(status)")
                
                self.db.conn.commit()
                self.logger.info("✅ Tabela events_cache criada com índices")
            else:
                self.logger.info("✅ Tabela events_cache já existe")
                
        except Exception as e:
            self.logger.error(f"❌ Erro ao criar tabela events_cache: {e}")
            raise
    
    def _parse_event_date(self, date_str: str) -> Optional[datetime]:
        """
        Converte string de data para datetime UTC
        """
        try:
            if isinstance(date_str, str):
                # Remove 'Z' e converte para formato ISO
                if date_str.endswith('Z'):
                    date_str = date_str[:-1] + '+00:00'
                return datetime.fromisoformat(date_str)
            return None
        except Exception as e:
            self.logger.debug(f"Erro ao parsear data '{date_str}': {e}")
            return None
    
    def _is_within_window(self, event_date: datetime, window_hours: int) -> bool:
        """
        Verifica se evento está dentro da janela de tempo
        """
        now = datetime.utcnow()
        window_end = now + timedelta(hours=window_hours)
        return now <= event_date <= window_end
    
    def _upsert_event(self, event: Dict) -> bool:
        """
        Insere ou atualiza evento na tabela events_cache
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Extrai dados do evento
            event_id = event.get('id', '')
            sport = event.get('sport', {}).get('slug', '') if isinstance(event.get('sport'), dict) else str(event.get('sport', ''))
            league = event.get('league', {}).get('slug', '') if isinstance(event.get('league'), dict) else str(event.get('league', ''))
            home = event.get('home', '')
            away = event.get('away', '')
            date_utc = event.get('commenceTime', event.get('date', ''))
            status = event.get('status', 'pending')
            
            # Valida dados obrigatórios
            if not all([event_id, sport, league, home, away, date_utc]):
                self.logger.debug(f"Evento inválido (dados faltando): {event_id}")
                return False
            
            # Converte data para string ISO
            if isinstance(date_utc, str):
                date_iso = date_utc
            else:
                date_iso = date_utc.isoformat() if hasattr(date_utc, 'isoformat') else str(date_utc)
            
            # UPSERT: tenta atualizar primeiro, se não existir, insere
            cursor.execute("""
                UPDATE events_cache 
                SET sport = ?, league = ?, home = ?, away = ?, date_utc = ?, 
                    status = ?, last_seen = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (sport, league, home, away, date_iso, status, event_id))
            
            if cursor.rowcount == 0:
                # Não existia, insere novo
                cursor.execute("""
                    INSERT INTO events_cache (id, sport, league, home, away, date_utc, status, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (event_id, sport, league, home, away, date_iso, status))
            
            self.db.conn.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao upsert evento {event.get('id', 'unknown')}: {e}")
            return False
    
    async def discover_events_usa(self, window_hours: int = 120) -> Dict:
        """
        Descobre eventos americanos e atualiza cache
        
        Args:
            window_hours: Janela de tempo em horas (padrão 120h = 5 dias)
            
        Returns:
            Dict com contadores por liga
        """
        self.logger.info(f"🔍 Iniciando descoberta de eventos USA (janela: {window_hours}h)")
        
        # Garante que tabela existe
        self._ensure_events_cache_table()
        
        # Contadores por liga
        league_counters = {}
        total_events = 0
        total_processed = 0
        
        # Combina sports e leagues
        sport_league_pairs = []
        for sport in self.usa_sports:
            for league in self.usa_leagues:
                sport_league_pairs.append((sport, league))
        
        self.logger.info(f"📊 Processando {len(sport_league_pairs)} combinações (sport, league)")
        
        for sport, league in sport_league_pairs:
            try:
                self.logger.info(f"🔍 Buscando eventos: {sport} - {league}")
                
                events_found = 0
                events_within_window = 0
                events_upserted = 0
                
                # Busca eventos paginados
                async for event in self.api_client.get_events_paginated(
                    sport_slug=sport,
                    league_slug=league,
                    status="pending",
                    limit=100
                ):
                    events_found += 1
                    total_processed += 1
                    
                    # Verifica se está dentro da janela de tempo
                    event_date = self._parse_event_date(event.get('commenceTime', event.get('date', '')))
                    if event_date and self._is_within_window(event_date, window_hours):
                        events_within_window += 1
                        
                        # Upsert no banco
                        if self._upsert_event(event):
                            events_upserted += 1
                            total_events += 1
                    else:
                        self.logger.debug(f"Evento fora da janela: {event.get('home', '')} vs {event.get('away', '')}")
                
                # Atualiza contadores
                league_counters[f"{sport}_{league}"] = {
                    'found': events_found,
                    'within_window': events_within_window,
                    'upserted': events_upserted
                }
                
                self.logger.info(f"✅ {sport}-{league}: {events_found} encontrados, {events_within_window} na janela, {events_upserted} upserted")
                
                # Pequena pausa entre ligas para rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"❌ Erro ao processar {sport}-{league}: {e}")
                league_counters[f"{sport}_{league}"] = {
                    'found': 0,
                    'within_window': 0,
                    'upserted': 0,
                    'error': str(e)
                }
        
        # Resultado final
        result = {
            'total_events': total_events,
            'total_processed': total_processed,
            'window_hours': window_hours,
            'leagues': league_counters,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.info(f"✅ Descoberta concluída: {total_events} eventos em {total_processed} processados")
        return result
    
    async def get_cached_events(self, sport: Optional[str] = None, league: Optional[str] = None, 
                              status: str = "pending", limit: int = 100) -> List[Dict]:
        """
        Busca eventos do cache local
        
        Args:
            sport: Filtrar por esporte (opcional)
            league: Filtrar por liga (opcional)
            status: Status dos eventos (padrão: pending)
            limit: Limite de resultados
            
        Returns:
            Lista de eventos do cache
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Monta query com filtros
            where_conditions = ["status = ?"]
            params = [status]
            
            if sport:
                where_conditions.append("sport = ?")
                params.append(sport)
            
            if league:
                where_conditions.append("league = ?")
                params.append(league)
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT id, sport, league, home, away, date_utc, status, last_seen, created_at
                FROM events_cache 
                WHERE {where_clause}
                ORDER BY date_utc ASC
                LIMIT ?
            """
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Converte para dict
            events = []
            for row in rows:
                events.append({
                    'id': row[0],
                    'sport': row[1],
                    'league': row[2],
                    'home': row[3],
                    'away': row[4],
                    'date_utc': row[5],
                    'status': row[6],
                    'last_seen': row[7],
                    'created_at': row[8]
                })
            
            self.logger.info(f"📋 Cache: {len(events)} eventos encontrados")
            return events
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao buscar cache: {e}")
            return []
    
    def get_cache_stats(self) -> Dict:
        """
        Retorna estatísticas do cache
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Conta por status
            cursor.execute("SELECT status, COUNT(*) FROM events_cache GROUP BY status")
            status_counts = dict(cursor.fetchall())
            
            # Conta por liga
            cursor.execute("SELECT league, COUNT(*) FROM events_cache GROUP BY league")
            league_counts = dict(cursor.fetchall())
            
            # Total
            cursor.execute("SELECT COUNT(*) FROM events_cache")
            total = cursor.fetchone()[0]
            
            return {
                'total_events': total,
                'by_status': status_counts,
                'by_league': league_counts,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao obter stats do cache: {e}")
            return {'error': str(e)}

# Função de conveniência para uso externo
async def discover_events_usa(window_hours: int = 120) -> Dict:
    """
    Função de conveniência para descobrir eventos USA
    """
    scanner = USEventScanner()
    return await scanner.discover_events_usa(window_hours)
