"""
Bot EV+ - formatação e envio de alertas
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from telegram import Bot
from telegram.error import TelegramError

from config import get_telegram_token
from database import SQLiteConnectionPool, SQLiteConnectionConfig
from bot_core import definir_stake
from formatadores import formatar_ev, formatar_odd, formatar_stake
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

    async def enviar_alerta(self, chat_id: int, aposta: Dict[str, Any]):
        """
        Envia alerta de aposta para o usuário
        """
        try:
            # Formata o alerta
            mensagem = await self._formatar_alerta(aposta)
            
            # Envia a mensagem
            await self.bot.send_message(
                chat_id=chat_id,
                text=mensagem,
                parse_mode='Markdown',
                disable_web_page_preview=True
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

    async def _formatar_alerta(self, aposta: Dict[str, Any]) -> str:
        """
        Formata o alerta de aposta
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
            
            # Emojis baseados no esporte
            emoji_esporte = self._get_emoji_esporte(sport)
            
            # Monta a mensagem
            mensagem = f"""
🎯 **ALERTA EV+** {emoji_esporte}

🏆 **{home} vs {away}**
📊 **Liga:** {league}
🎲 **Mercado:** {market_type}
🎯 **Aposta:** {bet_side}
🏪 **Bookmaker:** {bookmaker}

💰 **Odd:** {odds_fmt}
📈 **EV:** {ev_pct}
💵 **Stake:** {stake_fmt}
⏰ **Tempo restante:** {tempo_restante}

🚀 **Boa sorte!** 🍀
            """
            
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
            
            # Parse da data/hora
            if 'T' in commence_time:
                jogo_time = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
            else:
                jogo_time = datetime.strptime(commence_time, "%Y-%m-%d %H:%M:%S")
            
            agora = datetime.now(jogo_time.tzinfo) if jogo_time.tzinfo else datetime.now()
            diferenca = jogo_time - agora
            
            if diferenca.total_seconds() < 0:
                return "Jogo iniciado"
            
            # Formata o tempo
            dias = diferenca.days
            horas, resto = divmod(diferenca.seconds, 3600)
            minutos, _ = divmod(resto, 60)
            
            if dias > 0:
                return f"{dias}d {horas}h {minutos}m"
            elif horas > 0:
                return f"{horas}h {minutos}m"
            else:
                return f"{minutos}m"
                
        except Exception as e:
            logger.error(f"Erro ao calcular tempo restante: {e}")
            return "N/A"

    def _get_emoji_esporte(self, sport: str) -> str:
        """
        Retorna emoji baseado no esporte
        """
        emojis = {
            'soccer': '⚽',
            'basketball': '🏀',
            'tennis': '🎾',
            'volleyball': '🏐',
            'handball': '🤾',
            'americanfootball': '🏈',
            'baseball': '⚾',
            'icehockey': '🏒',
            'cricket': '🏏',
            'rugby': '🏉'
        }
        return emojis.get(sport.lower(), '🏆')

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

# Instância global do alert sender
alert_sender = AlertSender()

async def enviar_alerta(chat_id: int, aposta: Dict[str, Any]):
    """
    Função global para enviar alerta
    """
    await alert_sender.enviar_alerta(chat_id, aposta)

def get_alert_sender() -> AlertSender:
    """
    Retorna instância do alert sender
    """
    return alert_sender