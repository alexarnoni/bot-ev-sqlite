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

    async def enviar_alerta(self, chat_id, aposta: Dict[str, Any]):
        """
        Envia alerta de aposta para o usuário
        """
        try:
            # Converte chat_id para int se necessário
            chat_id_int = int(chat_id) if isinstance(chat_id, str) else chat_id
            
            # Formata o alerta
            mensagem = await self._formatar_alerta(aposta)
            
            # Envia a mensagem
            await self.bot.send_message(
                chat_id=chat_id_int,
                text=mensagem,
                parse_mode='HTML',
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

    async def _formatar_alerta_instantaneo(self, aposta: Dict[str, Any], stake: float) -> str:
        """
        Formata alerta instantâneo para EV+ 10% com destaque especial
        Usa formatador específico para player props
        """
        try:
            # Verificar se é player prop
            if aposta.get('is_player_prop'):
                # Import seguro
                try:
                    from formatadores import montar_nome_mercado, formatar_data_jogo, safe_html
                except Exception:
                    def montar_nome_mercado(e): 
                        return (e.get("market_name") or (e.get("market") or {}).get("name") or "").title()
                    def formatar_data_jogo(s): 
                        return ""
                    def safe_html(s): 
                        import html as _h; return _h.escape(s or "")

                # Monta nome do mercado
                nome_mercado = montar_nome_mercado(aposta)

                # Extrai jogador do texto entre parênteses
                player = ""
                m = re.search(r'\(([^)]+)\)', nome_mercado)
                if m:
                    player = m.group(1).strip()
                else:
                    player = aposta.get('player', '') or aposta.get('selection', '')

                # Tipo de prop (remove jogador entre parênteses)
                prop_tipo = re.sub(r'\s*\(.*?\)', '', nome_mercado).strip()

                # Linha (hdp, total, line, points)
                linha = None
                for field in ['hdp', 'total', 'line', 'points']:
                    val = aposta.get(field)
                    if val is not None:
                        try:
                            linha = float(val)
                            break
                        except (TypeError, ValueError):
                            continue

                # Odd principal
                odd = aposta.get('odds') or aposta.get('bet365_odds') or aposta.get('odds_home') or aposta.get('odds_away') or aposta.get('price') or "?"
                try:
                    odd_float = float(odd)
                    odd_txt = f"{odd_float:.2f}"
                except (TypeError, ValueError):
                    odd_txt = str(odd)

                # Outros campos
                book = safe_html(aposta.get('bookmaker', ''))
                liga = safe_html(aposta.get('league', ''))
                home = safe_html((aposta.get('home') or '').strip())
                away = safe_html((aposta.get('away') or '').strip())
                quando = formatar_data_jogo(aposta.get('commence_time'))

                # EV
                ev_val = aposta.get('ev')
                ev_txt = None
                if ev_val is not None:
                    try:
                        ev_float = float(ev_val)
                        if ev_float > 0:
                            ev_txt = f"{ev_float:.2%}"
                    except (TypeError, ValueError):
                        pass

                # Monta mensagem
                msg = "🚨 <b>ALERTA INSTANTÂNEO - EV+ 10%!</b> 🚨\n\n"
                msg += "🎯 <b>PLAYER PROP</b>\n"
                
                if liga:
                    msg += f"🏆 <b>{liga}</b>\n\n"
                
                if player:
                    msg += f"👤 <b>{safe_html(player)}</b>\n"
                
                if prop_tipo:
                    if linha is not None:
                        msg += f"📊 {safe_html(prop_tipo)} — <b>{linha}</b>\n"
                    else:
                        msg += f"📊 {safe_html(prop_tipo)}\n"
                
                if ev_txt:
                    msg += f"📈 <b>EV:</b> {ev_txt}\n"
                
                if home and away:
                    msg += f"🏟️ {home} vs {away}\n"
                
                if quando:
                    msg += f"🗓️ {quando}\n"
                
                msg += f"\n💰 <b>Odd:</b> {odd_txt}"
                if book:
                    msg += f"\n🏦 {book}"

                # Link
                href = None
                raw_bet = aposta.get('raw_bet', {})
                if isinstance(raw_bet, dict):
                    bookmaker_odds = raw_bet.get('bookmakerOdds', {})
                    if isinstance(bookmaker_odds, dict):
                        href = bookmaker_odds.get('href')
                if not href:
                    href = aposta.get('event_url')
                
                if href:
                    msg += f"\n🔗 <a href=\"{href}\">Abrir na casa</a>"

                # Mini comparador Over/Under
                try:
                    # Tenta usar dados do ev_info se disponível
                    ev_info = aposta.get('ev_info', {})
                    best_over = ev_info.get('best_over')
                    best_under = ev_info.get('best_under')
                    
                    if not best_over or not best_under:
                        # Fallback: calcula diretamente dos dados
                        odds_info = raw_bet.get('bookmakerOdds', {})
                        if isinstance(odds_info, dict):
                            melhores = []
                            for bk_name, odds in odds_info.items():
                                if isinstance(odds, dict):
                                    try:
                                        over_val = float(odds.get('over', 0))
                                        under_val = float(odds.get('under', 0))
                                        if over_val > 0 and under_val > 0:
                                            melhores.append((safe_html(bk_name), over_val, under_val))
                                    except (TypeError, ValueError):
                                        continue

                            if melhores:
                                best_over = max(melhores, key=lambda x: x[1])
                                best_under = max(melhores, key=lambda x: x[2])
                    
                    if best_over and best_under:
                        msg += "\n\n📊 <b>Comparador (Melhores Odds)</b>\n"
                        msg += f"⬆️ Over: {best_over[1]:.2f} ({best_over[0]})\n"
                        msg += f"⬇️ Under: {best_under[1]:.2f} ({best_under[0]})\n"
                except Exception:
                    pass

                return msg
            
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
            from formatadores import formatar_data_brasileira, formatar_nome_esporte, formatar_nome_bookmaker, formatar_market_name
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
            
            # MENSAGEM PADRONIZADA
            mensagem = f"""{emoji_esporte} <b>{home} vs {away}</b>
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
            logger.error(f"Erro ao formatar alerta instantâneo: {e}")
            return f"🚨 Erro na formatação do alerta: {e}"

    async def _formatar_alerta(self, aposta: Dict[str, Any]) -> str:
        """
        Formata o alerta de aposta com layout melhorado
        Usa formatador específico para player props
        """
        try:
            # Verificar se é player prop
            if aposta.get('is_player_prop'):
                # Import seguro
                try:
                    from formatadores import montar_nome_mercado, formatar_data_jogo, safe_html
                except Exception:
                    def montar_nome_mercado(e): 
                        return (e.get("market_name") or (e.get("market") or {}).get("name") or "").title()
                    def formatar_data_jogo(s): 
                        return ""
                    def safe_html(s): 
                        import html as _h; return _h.escape(s or "")

                # Monta nome do mercado
                nome_mercado = montar_nome_mercado(aposta)

                # Extrai jogador do texto entre parênteses
                player = ""
                m = re.search(r'\(([^)]+)\)', nome_mercado)
                if m:
                    player = m.group(1).strip()
                else:
                    player = aposta.get('player', '') or aposta.get('selection', '')

                # Tipo de prop (remove jogador entre parênteses)
                prop_tipo = re.sub(r'\s*\(.*?\)', '', nome_mercado).strip()

                # Linha (hdp, total, line, points)
                linha = None
                for field in ['hdp', 'total', 'line', 'points']:
                    val = aposta.get(field)
                    if val is not None:
                        try:
                            linha = float(val)
                            break
                        except (TypeError, ValueError):
                            continue

                # Odd principal
                odd = aposta.get('odds') or aposta.get('bet365_odds') or aposta.get('odds_home') or aposta.get('odds_away') or aposta.get('price') or "?"
                try:
                    odd_float = float(odd)
                    odd_txt = f"{odd_float:.2f}"
                except (TypeError, ValueError):
                    odd_txt = str(odd)

                # Outros campos
                book = safe_html(aposta.get('bookmaker', ''))
                liga = safe_html(aposta.get('league', ''))
                home = safe_html((aposta.get('home') or '').strip())
                away = safe_html((aposta.get('away') or '').strip())
                quando = formatar_data_jogo(aposta.get('commence_time'))

                # EV
                ev_val = aposta.get('ev')
                ev_txt = None
                if ev_val is not None:
                    try:
                        ev_float = float(ev_val)
                        if ev_float > 0:
                            ev_txt = f"{ev_float:.2%}"
                    except (TypeError, ValueError):
                        pass

                # Monta mensagem
                msg = "🎯 <b>PLAYER PROP</b>\n"
                
                if liga:
                    msg += f"🏆 <b>{liga}</b>\n\n"
                
                if player:
                    msg += f"👤 <b>{safe_html(player)}</b>\n"
                
                if prop_tipo:
                    if linha is not None:
                        msg += f"📊 {safe_html(prop_tipo)} — <b>{linha}</b>\n"
                    else:
                        msg += f"📊 {safe_html(prop_tipo)}\n"
                
                if ev_txt:
                    msg += f"📈 <b>EV:</b> {ev_txt}\n"
                
                if home and away:
                    msg += f"🏟️ {home} vs {away}\n"
                
                if quando:
                    msg += f"🗓️ {quando}\n"
                
                msg += f"\n💰 <b>Odd:</b> {odd_txt}"
                if book:
                    msg += f"\n🏦 {book}"

                # Link
                href = None
                raw_bet = aposta.get('raw_bet', {})
                if isinstance(raw_bet, dict):
                    bookmaker_odds = raw_bet.get('bookmakerOdds', {})
                    if isinstance(bookmaker_odds, dict):
                        href = bookmaker_odds.get('href')
                if not href:
                    href = aposta.get('event_url')
                
                if href:
                    msg += f"\n🔗 <a href=\"{href}\">Abrir na casa</a>"

                # Mini comparador Over/Under
                try:
                    # Tenta usar dados do ev_info se disponível
                    ev_info = aposta.get('ev_info', {})
                    best_over = ev_info.get('best_over')
                    best_under = ev_info.get('best_under')
                    
                    if not best_over or not best_under:
                        # Fallback: calcula diretamente dos dados
                        odds_info = raw_bet.get('bookmakerOdds', {})
                        if isinstance(odds_info, dict):
                            melhores = []
                            for bk_name, odds in odds_info.items():
                                if isinstance(odds, dict):
                                    try:
                                        over_val = float(odds.get('over', 0))
                                        under_val = float(odds.get('under', 0))
                                        if over_val > 0 and under_val > 0:
                                            melhores.append((safe_html(bk_name), over_val, under_val))
                                    except (TypeError, ValueError):
                                        continue

                            if melhores:
                                best_over = max(melhores, key=lambda x: x[1])
                                best_under = max(melhores, key=lambda x: x[2])
                    
                    if best_over and best_under:
                        msg += "\n\n📊 <b>Comparador (Melhores Odds)</b>\n"
                        msg += f"⬆️ Over: {best_over[1]:.2f} ({best_over[0]})\n"
                        msg += f"⬇️ Under: {best_under[1]:.2f} ({best_under[0]})\n"
                except Exception:
                    pass

                return msg
            
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
            from formatadores import formatar_data_brasileira, formatar_nome_esporte, formatar_nome_bookmaker, formatar_market_name
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
            
            mensagem = f"""{emoji_esporte} <b>{home} vs {away}</b>
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

# Instância global do alert sender
alert_sender = AlertSender()

async def enviar_alerta(chat_id: int, aposta: Dict[str, Any]):
    """
    Função global para enviar alerta
    """
    await alert_sender.enviar_alerta(chat_id, aposta)

async def enviar_alerta_instantaneo(chat_id, evento: Dict[str, Any], stake: float):
    """
    Envia alerta instantâneo para EV+ 10%
    """
    try:
        # Formata o alerta com indicação de INSTANTÂNEO
        mensagem = await alert_sender._formatar_alerta_instantaneo(evento, stake)
        
        # Converte chat_id para int se necessário
        chat_id_int = int(chat_id) if isinstance(chat_id, str) else chat_id
        
        # Envia IMEDIATAMENTE
        await alert_sender.bot.send_message(
            chat_id=chat_id_int,
            text=mensagem,
            parse_mode='HTML',
            disable_web_page_preview=True
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
            await alert_sender.enviar_alerta(chat_id_int, aposta)
            # Pequena pausa entre alertas para evitar spam
            await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"Erro ao enviar batch para {chat_id}: {e}")
        raise

def get_alert_sender() -> AlertSender:
    """
    Retorna instância do alert sender
    """
    return alert_sender