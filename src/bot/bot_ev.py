"""
Bot EV+ - formatação e envio de alertas
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from src.core.config import get_telegram_token, THRESHOLD_EV_ALTO, FEED_ID
from src.bot.bets_tracker import BetsTracker, gerar_alert_hash, DadosAlerta
from src.core.database import get_db
from src.core.database import SQLiteConnectionPool, SQLiteConnectionConfig
from src.bot.bot_core import definir_stake
from src.utils.formatadores import formatar_ev, formatar_odd, formatar_stake
import os

logger = logging.getLogger(__name__)

# Configuração do banco de dados
def get_database_path():
    feed_id = os.getenv("FEED_ID", "default")
    return os.path.join(os.getcwd(), "data", feed_id, "bot.db")

db_config = SQLiteConnectionConfig(
    database_path=get_database_path(),
    max_connections=10,
    timeout=30.0
)
db_pool = SQLiteConnectionPool(db_config)

class AlertSender:
    def __init__(self):
        self.bot_token = get_telegram_token()
        self.bot = Bot(token=self.bot_token)
        self.db_pool = db_pool
        self._bets_tracker = BetsTracker(get_db())

    def _montar_keyboard(self, bet_id: int) -> InlineKeyboardMarkup:
        """Retorna InlineKeyboardMarkup com botões Apostei/Pulei."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Apostei", callback_data=f"bet_yes:{bet_id}"),
                InlineKeyboardButton("❌ Pulei", callback_data=f"bet_no:{bet_id}"),
            ]
        ])

    async def enviar_alerta(self, chat_id, aposta: Dict[str, Any]):
        """
        Envia alerta de aposta para o usuário com botões de tracking.
        """
        try:
            # Converte chat_id para int se necessário
            chat_id_int = int(chat_id) if isinstance(chat_id, str) else chat_id
            chat_id_str = str(chat_id)

            # Registra alerta no tracker e obtém bet_id
            alert_hash = gerar_alert_hash(
                chat_id_str,
                aposta.get('home', ''),
                aposta.get('away', ''),
                aposta.get('market_type', ''),
                aposta.get('bet_side', ''),
                aposta.get('bookmaker', ''),
                aposta.get('commence_time', ''),
            )
            dados_alerta: DadosAlerta = {
                "home": aposta.get('home', ''),
                "away": aposta.get('away', ''),
                "league": aposta.get('league', ''),
                "sport": aposta.get('sport', ''),
                "market_type": aposta.get('market_type', ''),
                "bet_side": aposta.get('bet_side', ''),
                "bookmaker": aposta.get('bookmaker', ''),
                "odd_alerta": aposta.get('bet365_odds', 0),
                "ev_alerta": aposta.get('ev', 0),
                "commence_time": aposta.get('commence_time', ''),
            }
            bet_id = self._bets_tracker.registrar_alerta(alert_hash, chat_id_str, FEED_ID, dados_alerta)

            # Escolhe template baseado no EV
            ev = aposta.get('ev', 0)
            if ev >= THRESHOLD_EV_ALTO:
                mensagem = await self._formatar_alerta_destacado(aposta)
            else:
                mensagem = await self._formatar_alerta_normal(aposta)

            # Monta keyboard com bet_id
            keyboard = self._montar_keyboard(bet_id)

            # Envia a mensagem com botões
            await self.bot.send_message(
                chat_id=chat_id_int,
                text=mensagem,
                parse_mode='HTML',
                disable_web_page_preview=True,
                reply_markup=keyboard,
            )
            
            logger.info(f"✅ Alerta enviado para {chat_id}: {aposta.get('home', '')} vs {aposta.get('away', '')}")
            
        except TelegramError as e:
            if "blocked" in str(e).lower():
                logger.warning(f"⚠️ Usuário {chat_id} bloqueou o bot")
                await self._marcar_usuario_inativo(chat_id)
            else:
                logger.error(f"❌ Erro ao enviar alerta para {chat_id}: {e}")
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao enviar alerta: {e}")

    async def _formatar_alerta_destacado(self, aposta: Dict[str, Any], stake: float = None) -> str:
        """
        Template destacado para ev >= THRESHOLD_EV_ALTO.
        Inicia com: '🚨🚨 ALERTA EV ALTO 🚨🚨'
        """
        try:
            # Dados básicos
            home = aposta.get('home', '')
            away = aposta.get('away', '')
            league = aposta.get('league', '')
            sport = aposta.get('sport', '')
            market_type = aposta.get('market_type', '')
            bet_side = aposta.get('bet_side', '')
            odds = aposta.get('bet365_odds', 0)
            ev = aposta.get('ev', 0)
            bookmaker = aposta.get('bookmaker', '')
            commence_time = aposta.get('commence_time', '')
            
            # Formata valores
            ev_pct = formatar_ev(ev)
            odds_fmt = formatar_odd(odds)
            stake_fmt = formatar_stake(stake)
            
            # Calcula tempo restante
            tempo_restante = self._calcular_tempo_restante(commence_time)
            
            # Formata data completa
            from src.utils.formatadores import formatar_data_brasileira, formatar_nome_esporte, formatar_nome_bookmaker, formatar_market_name
            data_completa = formatar_data_brasileira(commence_time)
            esporte_fmt = formatar_nome_esporte(sport)
            bookmaker_fmt = formatar_nome_bookmaker(bookmaker)
            
            # Formata mercado com valor (hdp ou total)
            mercado_fmt = formatar_market_name(market_type, aposta=aposta)
            
            # Emojis baseados no esporte e país
            emoji_esporte = self._get_emoji_esporte(sport)
            bandeira_pais = self._get_bandeira_pais(league, aposta)
            
            # Monta a mensagem com layout melhorado
            link_evento = aposta.get('bet_url') or aposta.get('event_url') 
            
            # Formata o link como hiperlink HTML se disponível
            if link_evento:
                link_formatado = f'<a href="{link_evento}">🔗 Abrir na {bookmaker_fmt}</a>'
            else:
                link_formatado = f"🔗 Abrir na {bookmaker_fmt} (link não disponível)"
            
            # MENSAGEM PADRONIZADA — TEMPLATE DESTACADO
            mensagem = f"""🚨🚨 <b>ALERTA EV ALTO</b> 🚨🚨

{emoji_esporte} <b>{home} vs {away}</b>
{bandeira_pais} <b>{league}</b>
<b>📌 Mercado:</b> {mercado_fmt}
<b>🔢 Odd {bookmaker_fmt}:</b> {odds_fmt}
<b>📈 Valor Esperado (EV):</b> ⭐ {ev_pct}
<b>🎯 Stake:</b> {stake_fmt}
<b>🗓️ Data do Jogo:</b> {data_completa}
<b>⏳ Faltam:</b> {tempo_restante}
⚡ <b>Aposte rápido</b>
{link_formatado}"""
            
            return mensagem.strip()
            
        except Exception as e:
            logger.error(f"Erro ao formatar alerta destacado: {e}")
            return f"🚨 Erro na formatação do alerta: {e}"

    async def _formatar_alerta_normal(self, aposta: Dict[str, Any]) -> str:
        """
        Template normal para ev < THRESHOLD_EV_ALTO.
        Inicia com: '🟢 Alerta EV+'
        """
        try:
            # Dados básicos
            home = aposta.get('home', '')
            away = aposta.get('away', '')
            league = aposta.get('league', '')
            sport = aposta.get('sport', '')
            market_type = aposta.get('market_type', '')
            bet_side = aposta.get('bet_side', '')
            odds = aposta.get('bet365_odds', 0)
            ev = aposta.get('ev', 0)
            bookmaker = aposta.get('bookmaker', '')
            commence_time = aposta.get('commence_time', '')
            
            # Calcula stake
            stake = definir_stake(ev, odds)
            
            # Formata valores
            ev_pct = formatar_ev(ev)
            odds_fmt = formatar_odd(odds)
            stake_fmt = formatar_stake(stake)
            
            # Calcula tempo restante
            tempo_restante = self._calcular_tempo_restante(commence_time)
            
            # Formata data completa
            from src.utils.formatadores import formatar_data_brasileira, formatar_nome_esporte, formatar_nome_bookmaker, formatar_market_name
            data_completa = formatar_data_brasileira(commence_time)
            esporte_fmt = formatar_nome_esporte(sport)
            bookmaker_fmt = formatar_nome_bookmaker(bookmaker)
            
            # Formata mercado com valor (hdp ou total)
            mercado_fmt = formatar_market_name(market_type, aposta=aposta)
            
            # Emojis baseados no esporte e país
            emoji_esporte = self._get_emoji_esporte(sport)
            bandeira_pais = self._get_bandeira_pais(league, aposta)
            
            # Monta a mensagem com layout melhorado
            link_evento = aposta.get('bet_url') or aposta.get('event_url') 
            
            # Formata o link como hiperlink HTML se disponível
            if link_evento:
                link_formatado = f'<a href="{link_evento}">🔗 Abrir na {bookmaker_fmt}</a>'
            else:
                link_formatado = f"🔗 Abrir na {bookmaker_fmt} (link não disponível)"
            
            mensagem = f"""🟢 <b>Alerta EV+</b>

{emoji_esporte} <b>{home} vs {away}</b>
{bandeira_pais} <b>{league}</b>
<b>📌 Mercado:</b> {mercado_fmt}
<b>🔢 Odd {bookmaker_fmt}:</b> {odds_fmt}
<b>📈 Valor Esperado (EV):</b> {ev_pct}
<b>🎯 Stake:</b> {stake_fmt}
<b>🗓️ Data do Jogo:</b> {data_completa}
<b>⏳ Faltam:</b> {tempo_restante}
{link_formatado}"""
            
            return mensagem.strip()
            
        except Exception as e:
            logger.error(f"Erro ao formatar alerta: {e}")
            return "❌ Erro ao formatar alerta"

    def _calcular_tempo_restante(self, commence_time: str) -> str:
        """
        Calcula tempo restante até o início do jogo
        """
        try:
            if not commence_time:
                return "N/A"
            
            from datetime import timezone
            
            # Parse da data/hora
            if 'T' in commence_time:
                jogo_time = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
            else:
                jogo_time = datetime.strptime(commence_time, "%Y-%m-%d %H:%M:%S")
            
            # Se não tem timezone, assume UTC
            if jogo_time.tzinfo is None:
                jogo_time = jogo_time.replace(tzinfo=timezone.utc)
            
            # Usa UTC para comparação consistente
            agora = datetime.now(timezone.utc)
            diferenca = jogo_time - agora
            
            if diferenca.total_seconds() < 0:
                return "Jogo iniciado"
            
            # Formata o tempo
            dias = diferenca.days
            horas, resto = divmod(diferenca.seconds, 3600)
            minutos, _ = divmod(resto, 60)
            
            # Formata tempo
            if dias > 0:
                return f"{dias}d {horas}h {minutos}min"
            elif horas > 0:
                return f"{horas}h {minutos}min"
            else:
                return f"{minutos}min"
                
        except Exception as e:
            logger.error(f"Erro ao calcular tempo restante: {e}")
            return "N/A"

    def _get_emoji_esporte(self, sport: str) -> str:
        """
        Retorna emoji baseado no esporte
        Focado nos esportes disponíveis na API Odds
        """
        emojis = {
            # Esportes principais da API Odds
            'football': '⚽',
            'soccer': '⚽',
            'basketball': '🏀',
            'tennis': '🎾',
            'baseball': '⚾',
            'ice hockey': '🏒',
            'icehockey': '🏒',
            
            # Esportes adicionais que podem aparecer
            'volleyball': '🏐',
            'handball': '🤾',
            'americanfootball': '🏈',
            'american football': '🏈',
            'cricket': '🏏',
            'rugby': '🏉',
            'rugby league': '🏉',
            'rugby union': '🏉',
            
            # Esportes de combate
            'boxing': '🥊',
            'mma': '🥊',
            'ufc': '🥊',
            'kickboxing': '🥊',
            'muay thai': '🥊',
            'karate': '🥊',
            'taekwondo': '🥊',
            
            # Esportes de raquete
            'table tennis': '🏓',
            'badminton': '🏸',
            'squash': '🏸',
            'racquetball': '🏸',
            
            # Esports
            'esports': '🎮',
            'csgo': '🎮',
            'counter-strike': '🎮',
            'dota': '🎮',
            'lol': '🎮',
            'league of legends': '🎮',
            'valorant': '🎮',
            'overwatch': '🎮',
            'rocket league': '🎮',
            
            # Esportes automobilísticos
            'formula 1': '🏎️',
            'f1': '🏎️',
            'motogp': '🏍️',
            'nascar': '🏎️',
            'indycar': '🏎️',
            'rally': '🏎️',
            'wrc': '🏎️',
            
            # Outros esportes
            'golf': '⛳',
            'snooker': '🎱',
            'pool': '🎱',
            'billiards': '🎱',
            'darts': '🎯',
            'archery': '🏹',
            'swimming': '🏊',
            'athletics': '🏃',
            'cycling': '🚴',
            'equestrian': '🏇',
            'gymnastics': '🤸',
            'water polo': '🤽',
            'wrestling': '🤼',
            'fencing': '🤺',
            'weightlifting': '🏋️',
            'juggling': '🤹',
            'surfing': '🏄',
            'skateboarding': '🛹',
            'snowboarding': '🏂',
            'skiing': '⛷️',
            'ice skating': '⛸️',
            'figure skating': '⛸️'
        }
        return emojis.get(sport.lower(), '🏆')

    def _get_bandeira_pais(self, league: str, aposta: Dict[str, Any] = None) -> str:
        """
        Retorna bandeira do país baseado na liga e dados da API
        """
        league_lower = league.lower()
        
        # Primeiro, tenta detectar por padrões comuns na liga
        bandeira = self._detectar_pais_por_liga(league_lower)
        if bandeira != '🏆':
            return bandeira
        
        # Se não encontrou, tenta usar dados adicionais da API
        if aposta:
            bandeira = self._detectar_pais_por_dados_api(aposta)
            if bandeira != '🏆':
                return bandeira
        
        # Fallback: tenta detectar por nomes de times
        if aposta:
            bandeira = self._detectar_pais_por_times(aposta)
            if bandeira != '🏆':
                return bandeira
        
        return '🏆'  # Bandeira padrão
    
    def _detectar_pais_por_liga(self, league_lower: str) -> str:
        """
        Detecta país baseado em padrões comuns no nome da liga
        """
        # Padrões mais comuns primeiro (mais específicos)
        padroes = [
            # Competições internacionais - Emojis específicos
            ('champions league', '🏆'), ('europa league', '🏆'), ('uefa', '🏆'),
            ('copa libertadores', '🏆'), ('copa sudamericana', '🏆'),
            ('world cup', '🌍'), ('copa do mundo', '🌍'), ('fifa', '🌍'),
            ('euro', '🏆'), ('european championship', '🏆'),
            ('copa america', '🏆'), ('copa áfrica', '🏆'),
            ('asian cup', '🏆'), ('gold cup', '🏆'),
            ('conmebol', '🏆'), ('concacaf', '🏆'),
            ('afc', '🏆'), ('caf', '🏆'), ('ofc', '🏆'),
            
            # Competições continentais específicas
            ('conference league', '🏆'),
            ('copa do brasil', '🏆🇧🇷'), ('copa del rey', '🏆🇪🇸'),
            ('fa cup', '🏆🏴󠁧󠁢󠁥󠁮󠁧󠁿'), ('coppa italia', '🏆🇮🇹'),
            ('dfb pokal', '🏆🇩🇪'), ('coupe de france', '🏆🇫🇷'),
            ('taça de portugal', '🏆🇵🇹'), ('knvb beker', '🏆🇳🇱'),
            
            # Competições de clubes mundiais
            ('club world cup', '🌍'), ('mundial de clubes', '🌍'),
            ('supercopa', '🏆'), ('super cup', '🏆'),
            ('recopa', '🏆'), ('intercontinental', '🌍'),
            
            # Países principais
            ('brazil', '🇧🇷'), ('brasil', '🇧🇷'), ('brasileirão', '🇧🇷'),
            ('england', '🏴󠁧󠁢󠁥󠁮󠁧󠁿'), ('premier league', '🏴󠁧󠁢󠁥󠁮󠁧󠁿'),
            ('spain', '🇪🇸'), ('la liga', '🇪🇸'), ('espanha', '🇪🇸'),
            ('germany', '🇩🇪'), ('bundesliga', '🇩🇪'), ('alemanha', '🇩🇪'),
            ('italy', '🇮🇹'), ('serie a', '🇮🇹'), ('itália', '🇮🇹'),
            ('france', '🇫🇷'), ('ligue 1', '🇫🇷'), ('frança', '🇫🇷'),
            ('netherlands', '🇳🇱'), ('eredivisie', '🇳🇱'), ('holanda', '🇳🇱'),
            ('portugal', '🇵🇹'), ('primeira liga', '🇵🇹'),
            ('argentina', '🇦🇷'), ('primera división', '🇦🇷'),
            ('mexico', '🇲🇽'), ('méxico', '🇲🇽'), ('liga mx', '🇲🇽'),
            ('usa', '🇺🇸'), ('united states', '🇺🇸'), ('mls', '🇺🇸'),
            
            # Outros países
            ('russia', '🇷🇺'), ('turkey', '🇹🇷'), ('greece', '🇬🇷'),
            ('belgium', '🇧🇪'), ('switzerland', '🇨🇭'), ('austria', '🇦🇹'),
            ('poland', '🇵🇱'), ('croatia', '🇭🇷'), ('serbia', '🇷🇸'),
            ('romania', '🇷🇴'), ('bulgaria', '🇧🇬'), ('hungary', '🇭🇺'),
            ('norway', '🇳🇴'), ('sweden', '🇸🇪'), ('denmark', '🇩🇰'),
            ('finland', '🇫🇮'), ('japan', '🇯🇵'), ('china', '🇨🇳'),
            ('australia', '🇦🇺'), ('canada', '🇨🇦'), ('puerto rico', '🇵🇷'),
            ('colombia', '🇨🇴'), ('chile', '🇨🇱'), ('peru', '🇵🇪'),
            ('uruguay', '🇺🇾'), ('ecuador', '🇪🇨'), ('venezuela', '🇻🇪'),
            ('bolivia', '🇧🇴'), ('paraguay', '🇵🇾')
        ]
        
        for padrao, bandeira in padroes:
            if padrao in league_lower:
                return bandeira
        
        return '🏆'
    
    def _detectar_pais_por_dados_api(self, aposta: Dict[str, Any]) -> str:
        """
        Detecta país usando dados adicionais da API
        """
        # Tenta extrair país de campos como 'country', 'region', etc.
        campos_pais = ['country', 'region', 'location', 'venue_country']
        
        for campo in campos_pais:
            valor = aposta.get(campo, '').lower()
            if valor:
                return self._detectar_pais_por_liga(valor)
        
        return '🏆'
    
    def _detectar_pais_por_times(self, aposta: Dict[str, Any]) -> str:
        """
        Detecta país baseado nos nomes dos times
        """
        home = aposta.get('home', '').lower()
        away = aposta.get('away', '').lower()
        
        # Padrões de cidades/países nos nomes dos times
        padroes_times = [
            # Cidades brasileiras
            ('flamengo', '🇧🇷'), ('palmeiras', '🇧🇷'), ('santos', '🇧🇷'),
            ('corinthians', '🇧🇷'), ('são paulo', '🇧🇷'), ('fluminense', '🇧🇷'),
            ('botafogo', '🇧🇷'), ('vasco', '🇧🇷'), ('cruzeiro', '🇧🇷'),
            ('atlético', '🇧🇷'), ('grêmio', '🇧🇷'), ('internacional', '🇧🇷'),
            
            # Times europeus famosos
            ('real madrid', '🇪🇸'), ('barcelona', '🇪🇸'), ('atletico', '🇪🇸'),
            ('manchester', '🏴󠁧󠁢󠁥󠁮󠁧󠁿'), ('liverpool', '🏴󠁧󠁢󠁥󠁮󠁧󠁿'),
            ('arsenal', '🏴󠁧󠁢󠁥󠁮󠁧󠁿'), ('chelsea', '🏴󠁧󠁢󠁥󠁮󠁧󠁿'),
            ('bayern', '🇩🇪'), ('dortmund', '🇩🇪'), ('juventus', '🇮🇹'),
            ('milan', '🇮🇹'), ('inter', '🇮🇹'), ('psg', '🇫🇷'),
            ('ajax', '🇳🇱'), ('porto', '🇵🇹'), ('benfica', '🇵🇹'),
            
            # Times sul-americanos
            ('boca', '🇦🇷'), ('river', '🇦🇷'), ('racing', '🇦🇷'),
            ('america', '🇲🇽'), ('chivas', '🇲🇽'), ('tigres', '🇲🇽'),
            ('penarol', '🇺🇾'), ('nacional', '🇺🇾'), ('colo colo', '🇨🇱'),
            ('universidad', '🇨🇱'), ('millonarios', '🇨🇴'), ('nacional', '🇨🇴')
        ]
        
        for padrao, bandeira in padroes_times:
            if padrao in home or padrao in away:
                return bandeira
        
        return '🏆'

    async def _marcar_usuario_inativo(self, chat_id: int):
        """
        Marca usuário como inativo quando bloqueia o bot
        """
        try:
            async with self.db_pool.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET is_active = 0, updated_at = datetime('now')
                    WHERE chat_id = ?
                """, (chat_id,))
                
            logger.info(f"👤 Usuário {chat_id} marcado como inativo")
            
        except Exception as e:
            logger.error(f"Erro ao marcar usuário inativo: {e}")

    async def enviar_mensagem_admin(self, mensagem: str):
        """
        Envia mensagem para administradores
        """
        try:
            # Lista de admins (configurar via env)
            admin_chat_ids = [350780046]  # IDs dos admins
            
            for admin_id in admin_chat_ids:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=mensagem,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Erro ao enviar mensagem para admin {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para admins: {e}")

    async def enviar_broadcast(self, mensagem: str, chat_ids: list = None):
        """
        Envia mensagem para múltiplos usuários
        """
        try:
            if chat_ids is None:
                # Busca todos os usuários ativos
                async with self.db_pool.get_connection() as conn:
                    cursor = await conn.execute("""
                        SELECT chat_id FROM users WHERE is_active = 1
                    """)
                    chat_ids = [row['chat_id'] for row in await cursor.fetchall()]
            
            # Envia para cada usuário
            for chat_id in chat_ids:
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=mensagem,
                        parse_mode='Markdown'
                    )
                    await asyncio.sleep(0.1)  # Rate limit
                except Exception as e:
                    logger.error(f"Erro ao enviar broadcast para {chat_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Erro no broadcast: {e}")

# Instância lazy do alert sender
_alert_sender: AlertSender | None = None

def get_alert_sender() -> AlertSender:
    """Retorna instância singleton do AlertSender (lazy init)."""
    global _alert_sender
    if _alert_sender is None:
        _alert_sender = AlertSender()
    return _alert_sender

async def enviar_alerta(chat_id: int, aposta: Dict[str, Any]):
    """
    Função global para enviar alerta
    """
    await get_alert_sender().enviar_alerta(chat_id, aposta)

async def enviar_alerta_instantaneo(chat_id, evento: Dict[str, Any], stake: float):
    """
    Envia alerta instantâneo para EV+ 10% — sempre usa template destacado.
    """
    try:
        chat_id_int = int(chat_id) if isinstance(chat_id, str) else chat_id
        chat_id_str = str(chat_id)

        # Registra alerta no tracker e obtém bet_id
        alert_hash = gerar_alert_hash(
            chat_id_str,
            evento.get('home', ''),
            evento.get('away', ''),
            evento.get('market_type', ''),
            evento.get('bet_side', ''),
            evento.get('bookmaker', ''),
            evento.get('commence_time', ''),
        )
        dados_alerta: DadosAlerta = {
            "home": evento.get('home', ''),
            "away": evento.get('away', ''),
            "league": evento.get('league', ''),
            "sport": evento.get('sport', ''),
            "market_type": evento.get('market_type', ''),
            "bet_side": evento.get('bet_side', ''),
            "bookmaker": evento.get('bookmaker', ''),
            "odd_alerta": evento.get('bet365_odds', 0),
            "ev_alerta": evento.get('ev', 0),
            "commence_time": evento.get('commence_time', ''),
        }
        bet_id = get_alert_sender()._bets_tracker.registrar_alerta(alert_hash, chat_id_str, FEED_ID, dados_alerta)

        # Formata o alerta com template destacado
        mensagem = await get_alert_sender()._formatar_alerta_destacado(evento, stake)

        # Monta keyboard com bet_id
        keyboard = get_alert_sender()._montar_keyboard(bet_id)

        # Envia IMEDIATAMENTE com botões
        await get_alert_sender().bot.send_message(
            chat_id=chat_id_int,
            text=mensagem,
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
        
        logger.info(f"🚨 Alerta de alta prioridade enviado para {chat_id}: EV {evento.get('ev', 0):.2%}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar alerta instantâneo para {chat_id}: {e}")

async def enviar_alertas_batch(chat_id, batch: list):
    """
    Envia múltiplos alertas em batch
    """
    try:
        # Converte chat_id para int se necessário
        chat_id_int = int(chat_id) if isinstance(chat_id, str) else chat_id
        
        for aposta, stake in batch:
            await get_alert_sender().enviar_alerta(chat_id_int, aposta)
            # Pequena pausa entre alertas para evitar spam
            await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"Erro ao enviar batch para {chat_id}: {e}")
        raise
