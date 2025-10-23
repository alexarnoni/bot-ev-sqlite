"""
Handlers para Player Props do feed americano
"""
import asyncio
import logging
from typing import Dict, List, Optional
from database import get_db
from bot_ev_us.api_client_us import OddsApiUSClient
from bot_ev_us.comparador_props import extract_player_props, group_and_compare, render_props_message
from bot_ev_us.scanner_us import USEventScanner

class USPropsHandlers:
    def __init__(self):
        self.db = get_db()
        self.api_client = OddsApiUSClient()
        self.scanner = USEventScanner()
        self.logger = logging.getLogger(__name__)
    
    async def handle_usa_jogos(self, chat_id: int, liga: str = None) -> str:
        """
        /usa_jogos <liga> - Lista jogos próximos com botões
        """
        try:
            # Busca eventos do cache (próximas 120h)
            events = await self.scanner.get_cached_events(
                league=liga,
                status="pending",
                limit=50
            )
            
            if not events:
                return f"❌ Nenhum jogo encontrado para liga: {liga or 'todas'}"
            
            # Agrupa por liga se não especificada
            if liga:
                message = f"🏀 **Jogos {liga.upper()}** (próximas 120h)\n\n"
            else:
                message = "🏀 **Jogos Americanos** (próximas 120h)\n\n"
            
            # Formata lista de jogos
            for i, event in enumerate(events[:20], 1):  # Limita a 20 jogos
                home = event['home']
                away = event['away']
                league = event['league']
                date_str = event['date_utc'][:16].replace('T', ' ')  # Formato mais legível
                
                message += f"{i}. **{home} vs {away}**\n"
                message += f"   📅 {date_str} | 🏆 {league}\n"
                message += f"   🔎 Props | 🛰 Monitor\n\n"
            
            if len(events) > 20:
                message += f"... e mais {len(events) - 20} jogos"
            
            return message
            
        except Exception as e:
            self.logger.error(f"Erro em handle_usa_jogos: {e}")
            return f"❌ Erro ao buscar jogos: {e}"
    
    async def handle_props(self, chat_id: int, event_id: str, stat_type: str = None, casas: str = None) -> str:
        """
        /props <eventId> [statType] [casas] - Busca props do evento
        """
        try:
            # Busca odds do evento
            bookmakers = casas or "BetMGM,Betano,Bet365,Betfair Sportsbook,Novibet,Superbet"
            odds_data = await self.api_client.get_event_odds(int(event_id), bookmakers)
            
            if not odds_data:
                return f"❌ Nenhuma odd encontrada para evento {event_id}"
            
            # Extrai props
            props = extract_player_props(odds_data)
            if not props:
                return f"❌ Nenhum player prop encontrado para evento {event_id}"
            
            # Filtra por stat_type se especificado
            if stat_type:
                props = [p for p in props if p['stat'].lower() == stat_type.lower()]
                if not props:
                    return f"❌ Nenhum prop do tipo '{stat_type}' encontrado"
            
            # Agrupa e compara
            grouped = group_and_compare(props)
            
            # Renderiza mensagem
            message = f"🎯 **Player Props - Evento {event_id}**\n\n"
            if stat_type:
                message += f"📊 **Filtro: {stat_type}**\n\n"
            
            message += render_props_message(grouped, top=15)
            
            # Adiciona resumo
            message += f"\n📈 **Resumo:** {len(props)} props, {len(grouped)} combinações únicas"
            
            return message
            
        except Exception as e:
            self.logger.error(f"Erro em handle_props: {e}")
            return f"❌ Erro ao buscar props: {e}"
    
    async def handle_props_tipo(self, chat_id: int, event_id: str, stat_type: str) -> str:
        """
        /props_tipo <eventId> <statType> - Lista jogadores do tipo
        """
        try:
            # Busca odds do evento
            bookmakers = "BetMGM,Betano,Bet365,Betfair Sportsbook,Novibet,Superbet"
            odds_data = await self.api_client.get_event_odds(int(event_id), bookmakers)
            
            if not odds_data:
                return f"❌ Nenhuma odd encontrada para evento {event_id}"
            
            # Extrai props e filtra por tipo
            props = extract_player_props(odds_data)
            props_filtered = [p for p in props if p['stat'].lower() == stat_type.lower()]
            
            if not props_filtered:
                return f"❌ Nenhum prop do tipo '{stat_type}' encontrado"
            
            # Agrupa por jogador
            players = {}
            for prop in props_filtered:
                player = prop['player']
                if player not in players:
                    players[player] = []
                players[player].append(prop)
            
            # Ordena jogadores por melhor over odd
            sorted_players = sorted(players.items(), 
                                 key=lambda x: max(p['over'] for p in x[1]), 
                                 reverse=True)
            
            message = f"👥 **Jogadores - {stat_type}** (Evento {event_id})\n\n"
            
            for player, player_props in sorted_players[:15]:  # Top 15 jogadores
                # Encontra melhor linha para este jogador
                best_prop = max(player_props, key=lambda x: x['over'])
                line = best_prop['line']
                over_odd = best_prop['over']
                bookmaker = best_prop['bookmaker']
                
                message += f"🏀 **{player}**\n"
                message += f"   📊 Linha: {line} | Over: {over_odd} ({bookmaker})\n\n"
            
            if len(sorted_players) > 15:
                message += f"... e mais {len(sorted_players) - 15} jogadores"
            
            return message
            
        except Exception as e:
            self.logger.error(f"Erro em handle_props_tipo: {e}")
            return f"❌ Erro ao buscar jogadores: {e}"
    
    async def handle_props_watch_start(self, chat_id: int, event_id: str, interval: int = 60, 
                                     casas: str = None, stat_type: str = "*", player: str = "*") -> str:
        """
        /props_watch start <eventId> [interval] [casas] [statType] [player] - Inicia monitor
        """
        try:
            # Valida parâmetros
            if interval < 30:
                return "❌ Intervalo mínimo: 30 segundos"
            
            if interval > 3600:
                return "❌ Intervalo máximo: 3600 segundos (1 hora)"
            
            # Casas padrão se não especificadas
            if not casas:
                casas = "BetMGM,Betano,Bet365"
            
            # Verifica se evento existe no cache
            events = await self.scanner.get_cached_events(limit=1)
            event_exists = any(str(e['id']) == event_id for e in events)
            
            if not event_exists:
                return f"❌ Evento {event_id} não encontrado no cache"
            
            # Cria/atualiza monitor
            cursor = self.db.conn.cursor()
            
            # Remove monitor existente se houver
            cursor.execute("""
                DELETE FROM props_monitors 
                WHERE chat_id = ? AND event_id = ?
            """, (str(chat_id), event_id))
            
            # Insere novo monitor
            cursor.execute("""
                INSERT INTO props_monitors 
                (chat_id, event_id, bookmakers_csv, stat_filter, player_filter, interval_seconds, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (str(chat_id), event_id, casas, stat_type, player, interval))
            
            self.db.conn.commit()
            
            # Resposta
            message = f"🛰 **Monitor iniciado**\n\n"
            message += f"📊 **Evento:** {event_id}\n"
            message += f"⏱️ **Intervalo:** {interval}s\n"
            message += f"🏦 **Casas:** {casas}\n"
            message += f"📈 **Stat:** {stat_type}\n"
            message += f"👤 **Jogador:** {player}\n\n"
            message += f"✅ Monitor ativo! Use /props_watch stop {event_id} para parar."
            
            return message
            
        except Exception as e:
            self.logger.error(f"Erro em handle_props_watch_start: {e}")
            return f"❌ Erro ao iniciar monitor: {e}"
    
    async def handle_props_watch_stop(self, chat_id: int, event_id: str) -> str:
        """
        /props_watch stop <eventId> - Para monitor
        """
        try:
            cursor = self.db.conn.cursor()
            
            # Marca monitor como inativo
            cursor.execute("""
                UPDATE props_monitors 
                SET is_active = 0 
                WHERE chat_id = ? AND event_id = ?
            """, (str(chat_id), event_id))
            
            if cursor.rowcount == 0:
                return f"❌ Nenhum monitor ativo encontrado para evento {event_id}"
            
            self.db.conn.commit()
            
            return f"🛑 **Monitor parado** para evento {event_id}"
            
        except Exception as e:
            self.logger.error(f"Erro em handle_props_watch_stop: {e}")
            return f"❌ Erro ao parar monitor: {e}"
    
    async def handle_props_watch_list(self, chat_id: int) -> str:
        """
        /props_watch list - Lista monitores ativos
        """
        try:
            cursor = self.db.conn.cursor()
            
            cursor.execute("""
                SELECT event_id, bookmakers_csv, stat_filter, player_filter, interval_seconds
                FROM props_monitors 
                WHERE chat_id = ? AND is_active = 1
                ORDER BY created_at DESC
            """, (str(chat_id),))
            
            monitors = cursor.fetchall()
            
            if not monitors:
                return "📋 Nenhum monitor ativo"
            
            message = "🛰 **Monitores Ativos**\n\n"
            
            for monitor in monitors:
                event_id, casas, stat, player, interval = monitor
                message += f"📊 **Evento {event_id}**\n"
                message += f"   ⏱️ {interval}s | 🏦 {casas}\n"
                message += f"   📈 {stat} | 👤 {player}\n\n"
            
            return message
            
        except Exception as e:
            self.logger.error(f"Erro em handle_props_watch_list: {e}")
            return f"❌ Erro ao listar monitores: {e}"

# Instância global para uso nos handlers
us_props_handlers = USPropsHandlers()

# Funções de conveniência para integração com o bot
async def handle_usa_jogos(chat_id: int, liga: str = None) -> str:
    """Handler para /usa_jogos"""
    return await us_props_handlers.handle_usa_jogos(chat_id, liga)

async def handle_props(chat_id: int, event_id: str, stat_type: str = None, casas: str = None) -> str:
    """Handler para /props"""
    return await us_props_handlers.handle_props(chat_id, event_id, stat_type, casas)

async def handle_props_tipo(chat_id: int, event_id: str, stat_type: str) -> str:
    """Handler para /props_tipo"""
    return await us_props_handlers.handle_props_tipo(chat_id, event_id, stat_type)

async def handle_props_watch_start(chat_id: int, event_id: str, interval: int = 60, 
                                 casas: str = None, stat_type: str = "*", player: str = "*") -> str:
    """Handler para /props_watch start"""
    return await us_props_handlers.handle_props_watch_start(chat_id, event_id, interval, casas, stat_type, player)

async def handle_props_watch_stop(chat_id: int, event_id: str) -> str:
    """Handler para /props_watch stop"""
    return await us_props_handlers.handle_props_watch_stop(chat_id, event_id)

async def handle_props_watch_list(chat_id: int) -> str:
    """Handler para /props_watch list"""
    return await us_props_handlers.handle_props_watch_list(chat_id)
