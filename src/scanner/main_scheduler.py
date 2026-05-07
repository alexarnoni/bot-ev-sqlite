"""
Scheduler principal do Bot EV+ - Processa usuários usando cache global
Agora apenas processa usuários do feed atual usando snapshot global compartilhado
"""
import asyncio
import time
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from src.core.config import MAX_CONCURRENT_SCANS, FEED_ID
from src.core.database import get_db
from src.bot.bets_tracker import BetsTracker
from src.data.usuarios import get_user_manager
from src.data.cache import get_cache
from src.data.historico import get_history
from src.api.status import get_status
from src.api.rate_limiter import get_rate_limiter
from src.filters.filtros import evento_valido, aplicar_filtros_dinamicos, validar_filtros_usuario
from src.bot.bot_core import definir_stake
from src.bot.bot_ev import enviar_alertas_batch
from src.utils.utils import logger_geral, logger_scan, update_league_catalog, LIGAS_POR_REGIAO
from src.scanner.scan_cache import get_snapshot_cache
from src.utils.messages import no_events
from src.utils.metrics import record_alert_processing, measure_time, get_metrics_summary

class BotScheduler:
    def __init__(self):
        # Usa o event loop atual para jobs assíncronos
        self.scheduler = AsyncIOScheduler(event_loop=asyncio.get_event_loop())
        self.user_manager = get_user_manager()
        self.cache = get_cache()
        self.history = get_history()
        self.status = get_status()
        self.db = get_db()
        self.rate_limiter = get_rate_limiter()
        self.snapshot_cache = get_snapshot_cache()
        self.bets_tracker = BetsTracker(self.db)
        
        # Semáforo para controlar concorrência
        self.scan_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCANS)
        
        # Estatísticas
        self.stats = {
            'total_scans': 0,
            'total_alertas': 0,
            'ultimo_scan': None,
            'erros_cache': 0
        }
    
    def start(self):
        """Inicia o scheduler com jobs de processamento"""
        logger_geral.info(f"🚀 Configurando scheduler do feed {FEED_ID}...")
        
        # JOB PRINCIPAL: PROCESSAR USUÁRIOS A CADA 2 MINUTOS (usando cache global)
        self.scheduler.add_job(
            self.process_users_job,
            IntervalTrigger(minutes=2),  # ← SEMPRE 2 MINUTOS
            id='process_users',
            max_instances=1,
            replace_existing=True
        )
        
        # Limpeza a cada hora (cache e rate limiter)
        self.scheduler.add_job(
            self.cleanup_job,
            CronTrigger(minute=0),
            id='cleanup_hourly'
        )
        
        # Limpeza do banco (3h da manhã) - histórico e pendentes
        self.scheduler.add_job(
            self.cleanup_database_job,
            CronTrigger(hour=3),
            id='cleanup_daily'
        )
        
        # Estatísticas a cada 30 minutos
        self.scheduler.add_job(
            self.stats_job,
            IntervalTrigger(minutes=30),
            id='stats'
        )
        
        # Job de lembrete pós-jogo a cada 15 minutos
        self.scheduler.add_job(
            self.lembrete_pos_jogo_job,
            IntervalTrigger(minutes=15),
            id='lembrete_pos_jogo',
            max_instances=1,
            replace_existing=True,
        )
        
        # Job de expiração de alertas antigos a cada 30 minutos
        self.scheduler.add_job(
            self.expiracao_job,
            IntervalTrigger(minutes=30),
            id='expiracao_bets',
            max_instances=1,
            replace_existing=True,
        )
        
        # Inicia o scheduler
        self.scheduler.start()
        logger_geral.info(f"✅ Scheduler do feed {FEED_ID} iniciado (processamento a cada 2min)")
        
        # Log dos jobs ativos
        for job in self.scheduler.get_jobs():
            logger_geral.info(f"📅 Job ativo: {job.id} - {job.trigger}")
    
    @measure_time('feed_processing')
    async def process_users_job(self):
        """Job principal de processamento - executa a cada 2 minutos usando cache global"""
        async with self.scan_semaphore:
            try:
                logger_scan.info(f"👥 Iniciando processamento do feed {FEED_ID}...")
                start_time = time.time()
                
                # Calcula momento do processamento uma vez para consistência
                momento_processamento = datetime.now(timezone.utc)
                
                # Busca snapshot global compartilhado
                snapshot = self.snapshot_cache.get_snapshot(max_age_seconds=300)  # 5 minutos de tolerância
                if not snapshot:
                    logger_scan.warning("⚠️ Snapshot global não disponível ou expirado")
                    self.stats['erros_cache'] += 1
                    return
                
                todos_eventos = snapshot.get('eventos', [])
                if not todos_eventos:
                    logger_scan.info("📭 Nenhum evento no snapshot global")
                    return
                
                logger_scan.info(f"📊 Usando snapshot global com {len(todos_eventos)} eventos")
                
                # Busca usuários configurados do feed atual
                usuarios = self.user_manager.get_all_users()
                usuarios_configurados = [
                    user for user in usuarios 
                    if self.user_manager.usuario_configurado(user['chat_id'])
                ]
                
                if not usuarios_configurados:
                    logger_scan.info(f"⚠️ Nenhum usuário configurado no feed {FEED_ID}")
                    return
                
                logger_scan.info(f"👥 {len(usuarios_configurados)} usuários configurados no feed {FEED_ID}")
                
                # Processa eventos para cada usuário do feed atual
                total_alertas = 0
                for user in usuarios_configurados:
                    try:
                        alertas_enviados = await self._processar_usuario(user, todos_eventos, momento_processamento)
                        total_alertas += alertas_enviados
                    except Exception as e:
                        logger_scan.error(f"❌ Erro ao processar usuário {user['chat_id']}: {e}")
                
                # Atualiza estatísticas
                self.stats['total_scans'] += 1
                self.stats['total_alertas'] += total_alertas
                self.stats['ultimo_scan'] = datetime.now()
                
                # Atualiza catálogo de ligas
                update_league_catalog(LIGAS_POR_REGIAO)
                
                # Log final
                elapsed = time.time() - start_time
                logger_scan.info(f"✅ Processamento do feed {FEED_ID} concluído em {elapsed:.2f}s - {total_alertas} alertas enviados")
                
                # Registra métricas de processamento
                record_alert_processing(elapsed, total_alertas, True)
                
                # Atualiza status do sistema
                self.db.set_api_status(True, f"Feed {FEED_ID} funcionando normalmente")
                
            except Exception as e:
                logger_scan.error(f"❌ Erro no processamento do feed {FEED_ID}: {e}")
                self.db.set_api_status(False, f"Erro no feed {FEED_ID}", str(e))
                self.stats['erros_cache'] += 1
    
    async def _processar_usuario(self, user: dict, todos_eventos: list, momento_scan: datetime = None) -> int:
        """Processa eventos para um usuário específico"""
        chat_id = user['chat_id']
        
        # Busca filtros do usuário
        filtros = self.user_manager.get_user_complete(chat_id)
        if not filtros:
            return 0
        
        # Calcula janela de tempo dinâmica uma vez por usuário
        janela_tempo = None
        filtro_dias = filtros.get("filtro_dias")
        if filtro_dias:
            from src.filters.filtros import calcular_janela_tempo_dinamica
            janela_tempo = calcular_janela_tempo_dinamica(filtro_dias, momento_scan)
        
        # Filtra eventos válidos
        eventos_validos = []
        for evento in todos_eventos:
            if not evento_valido(evento, filtros):
                continue
            
            # Verifica filtros específicos do usuário (bookmakers, ligas, esportes)
            ligas_usuario = filtros.get('ligas', [])
            esportes_usuario = filtros.get('esportes', [])
            bookmakers_usuario = filtros.get('bookmakers', [])
            
            if not validar_filtros_usuario(evento, filtros, ligas_usuario, esportes_usuario, bookmakers_usuario):
                continue
            
            if not aplicar_filtros_dinamicos(evento, filtros, janela_tempo):
                continue
                
            eventos_validos.append(evento)
        
        if not eventos_validos:
            return 0
        
        # Remove duplicatas do cache
        eventos_novos = []
        for evento in eventos_validos:
            if not self.cache.is_duplicate(chat_id, evento):
                eventos_novos.append(evento)
        
        if not eventos_novos:
            return 0
        
        # Calcula stake e separa alertas por prioridade
        alertas_normais = []
        alertas_instantaneos = []
        
        for evento in eventos_novos:
            ev = evento.get('ev', 0)
            stake = definir_stake(ev, evento.get('bet365_odds', 0))
            
            if stake > 0:
                # EV+ 10% = instantâneo
                if ev >= 0.10:  # 10% em decimal
                    alertas_instantaneos.append((evento, stake))
                    logger_scan.info(f"🚨 Alerta de alta prioridade detectado para {chat_id}: EV {ev:.2%}")
                else:
                    alertas_normais.append((evento, stake))
        
        # Envia alertas instantâneos IMEDIATAMENTE
        alertas_enviados = 0
        for evento, stake in alertas_instantaneos:
            try:
                # Import local para evitar circular import
                from src.bot.bot_ev import enviar_alerta_instantaneo
                await enviar_alerta_instantaneo(chat_id, evento, stake)
                alertas_enviados += 1
                
                # Adiciona ao cache
                self.cache.add_alert(chat_id, evento)
                
            except Exception as e:
                logger_scan.error(f"Erro ao enviar alerta instantâneo para {chat_id}: {e}")
        
        # Envia alertas normais em batches
        if alertas_normais:
            for i in range(0, len(alertas_normais), 5):  # Batch de 5
                batch = alertas_normais[i:i+5]
                try:
                    await enviar_alertas_batch(chat_id, batch)
                    alertas_enviados += len(batch)
                
                    # Adiciona ao cache e histórico
                    for evento, stake in batch:
                        self.cache.add_alert(chat_id, evento)
                        self.history.add_alert(chat_id, evento, stake)
                
                except Exception as e:
                    logger_scan.error(f"❌ Erro ao enviar batch para {chat_id}: {e}")
        
        return alertas_enviados
    
    async def cleanup_job(self):
        """Job de limpeza a cada hora - cache e rate limiter"""
        try:
            logger_geral.info("🧹 Iniciando limpeza horária...")
            
            # Limpa cache antigo (> 7 dias)
            self.cache.clean_old_cache(7)
            
            # Limpa logs de rate limiting (> 2 horas)
            self.rate_limiter.clean_old_logs()
            
            logger_geral.info("✅ Limpeza horária concluída")
            
        except Exception as e:
            logger_geral.error(f"❌ Erro na limpeza horária: {e}")
    
    async def cleanup_database_job(self):
        """Job de limpeza do banco às 3h da manhã - histórico e pendentes"""
        try:
            logger_geral.info("🗄️ Iniciando limpeza diária do banco...")
            
            # Limpa histórico antigo (> 90 dias)
            self.db.clean_old_history(90)
            
            # Limpa alertas pendentes antigos (> 24 horas)
            self.db.clean_old_pending_alerts(24)
            
            # Limpa cache antigo (> 7 dias)
            self.cache.clean_old_cache(7)
            
            # Limpa logs de rate limiting antigos (> 2 horas)
            self.rate_limiter.clean_old_logs()
            
            logger_geral.info("✅ Limpeza diária do banco concluída")
            
        except Exception as e:
            logger_geral.error(f"❌ Erro na limpeza diária do banco: {e}")
    
    async def stats_job(self):
        """Job de estatísticas a cada 30 minutos"""
        try:
            logger_geral.info("📊 Coletando estatísticas...")
            
            # Estatísticas do sistema
            system_stats = self.history.get_system_stats()
            api_status = self.status.get_api_status()
            rate_limit_info = self.rate_limiter.get_rate_limit_info()
            
            logger_geral.info(f"📈 Stats: {system_stats}")
            logger_geral.info(f"🔌 API: {api_status}")
            logger_geral.info(f"⏱️ Rate Limit: {rate_limit_info}")
            
        except Exception as e:
            logger_geral.error(f"❌ Erro ao coletar estatísticas: {e}")
    
    async def lembrete_pos_jogo_job(self):
        """Job de lembrete pós-jogo — executa a cada 15 minutos."""
        try:
            from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
            from src.core.config import get_telegram_token
            from src.utils.formatadores import formatar_data_brasileira

            pendentes = self.bets_tracker.get_pendentes_para_lembrete()
            if not pendentes:
                return

            bot = Bot(token=get_telegram_token())

            for aposta in pendentes:
                chat_id = aposta['chat_id']
                bet_id = aposta['id']
                try:
                    texto = self._formatar_lembrete(aposta)
                    keyboard = self._montar_keyboard_resultado(bet_id)

                    await bot.send_message(
                        chat_id=int(chat_id),
                        text=texto,
                        parse_mode='HTML',
                        reply_markup=keyboard,
                        disable_web_page_preview=True,
                    )
                    self.bets_tracker.marcar_lembrete_enviado(bet_id)

                except Exception as e:
                    logger_geral.error(f"Falha lembrete bet_id={bet_id} chat_id={chat_id}: {e}")
                    novo = self.bets_tracker.incrementar_tentativa_lembrete(bet_id)
                    if novo >= 5:
                        self.bets_tracker.marcar_resultado_expirado(bet_id)
                        logger_geral.warning(f"Aposta bet_id={bet_id} expirada após {novo} tentativas")
                    continue

        except Exception as e:
            logger_geral.error(f"Erro no job lembrete_pos_jogo: {e}")

    async def expiracao_job(self):
        """Job de expiração — executa a cada 30 minutos."""
        try:
            expirados = self.bets_tracker.expirar_alertas_antigos()
            if expirados > 0:
                logger_geral.info(f"🗑️ {expirados} alertas expirados automaticamente")
        except Exception as e:
            logger_geral.error(f"Erro no job expiracao_bets: {e}")

    def _formatar_lembrete(self, aposta: dict) -> str:
        """Formata mensagem de lembrete pós-jogo."""
        from src.utils.formatadores import formatar_data_brasileira
        home = aposta.get('home', '')
        away = aposta.get('away', '')
        league = aposta.get('league', '')
        market = aposta.get('market_type', '')
        odd = aposta.get('odd_alerta', 0)
        valor = aposta.get('valor_apostado', 0)
        ct = aposta.get('commence_time_ajustado') or aposta.get('commence_time', '')
        data_fmt = formatar_data_brasileira(ct) if ct else "N/A"
        return (
            f"⏰ <b>Resultado pendente!</b>\n\n"
            f"⚽ <b>{home} vs {away}</b>\n"
            f"🏆 {league}\n"
            f"📌 Mercado: {market}\n"
            f"🔢 Odd: {odd:.2f}\n"
            f"💰 Apostado: R$ {valor:.2f}\n"
            f"🗓️ Jogo: {data_fmt}\n\n"
            f"Qual foi o resultado?"
        )

    def _montar_keyboard_resultado(self, bet_id: int):
        """Retorna keyboard com 5 botões de resultado."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 Ganhei", callback_data=f"bet_result_win:{bet_id}"),
                InlineKeyboardButton("🔴 Perdi", callback_data=f"bet_result_loss:{bet_id}"),
                InlineKeyboardButton("⚪ Empate", callback_data=f"bet_result_push:{bet_id}"),
            ],
            [
                InlineKeyboardButton("💸 Cashout", callback_data=f"bet_cashout:{bet_id}"),
                InlineKeyboardButton("⏰ Adiar 3h", callback_data=f"bet_postpone:{bet_id}"),
            ],
        ])
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do scheduler"""
        return {
            **self.stats,
            'feed_id': FEED_ID,
            'usuarios_ativos': len(self.user_manager.get_all_users())
        }
    
    def stop(self):
        """Para o scheduler"""
        self.scheduler.shutdown()
        logger_geral.info("🛑 Scheduler parado")

# Função principal para executar o scheduler
async def main():
    """Função principal do scheduler"""
    scheduler = BotScheduler()
    
    try:
        scheduler.start()
        logger_geral.info(f"🤖 Bot EV+ Feed {FEED_ID} iniciado")
        
        # Mantém o scheduler rodando
        while True:
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        logger_geral.info("🛑 Interrompido pelo usuário")
    except Exception as e:
        logger_geral.error(f"❌ Erro fatal: {e}")
    finally:
        scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())
