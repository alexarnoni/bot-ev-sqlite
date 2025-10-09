"""
Scheduler principal do Bot EV+ com job fixo de 2 minutos
"""
import asyncio
import time
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from config import MAX_CONCURRENT_SCANS, FEED_ID
from database import get_db
from api_client import OddsAPIClient
from usuarios import get_user_manager
from cache import get_cache
from historico import get_history
from status import get_status
from database import get_db
from rate_limiter import get_rate_limiter
from filtros import evento_valido, aplicar_filtros_dinamicos
from bot_core import definir_stake
from bot_ev import enviar_alertas_batch
from utils import logger_geral, logger_scan, update_league_catalog, LIGAS_POR_REGIAO

class BotScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.api_client = OddsAPIClient()
        self.user_manager = get_user_manager()
        self.cache = get_cache()
        self.history = get_history()
        self.status = get_status()
        self.db = get_db()
        self.rate_limiter = get_rate_limiter()
        
        # Semáforo para controlar concorrência
        self.scan_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCANS)
        
        # Estatísticas
        self.stats = {
            'total_scans': 0,
            'total_eventos': 0,
            'total_alertas': 0,
            'ultimo_scan': None,
            'erros_api': 0
        }
    
    def start(self):
        """Inicia o scheduler com todos os jobs"""
        logger_geral.info("🚀 Configurando jobs do scheduler...")
        
        # JOB PRINCIPAL: SCAN A CADA 2 MINUTOS (FIXO)
        self.scheduler.add_job(
            self.main_scan_job,
            IntervalTrigger(minutes=2),  # ← SEMPRE 2 MINUTOS
            id='main_scan',
            max_instances=1,
            replace_existing=True
        )
        
        # Limpeza a cada hora
        self.scheduler.add_job(
            self.cleanup_job,
            CronTrigger(minute=0),
            id='cleanup'
        )
        
        # Limpeza do banco (3h da manhã)
        self.scheduler.add_job(
            self.cleanup_database_job,
            CronTrigger(hour=3),
            id='cleanup_db'
        )
        
        # Estatísticas a cada 30 minutos
        self.scheduler.add_job(
            self.stats_job,
            IntervalTrigger(minutes=30),
            id='stats'
        )
        
        # Inicia o scheduler
        self.scheduler.start()
        logger_geral.info("✅ Scheduler iniciado (scan 2min fixo)")
        
        # Log dos jobs ativos
        for job in self.scheduler.get_jobs():
            logger_geral.info(f"📅 Job ativo: {job.id} - {job.trigger}")
    
    async def main_scan_job(self):
        """Job principal de scan - executa a cada 2 minutos"""
        async with self.scan_semaphore:
            try:
                logger_scan.info("🔍 Iniciando scan principal...")
                start_time = time.time()
                
                # Calcula momento do scan uma vez para consistência
                momento_scan = datetime.now(timezone.utc)
                
                # Busca usuários configurados
                usuarios = self.user_manager.get_all_users()
                usuarios_configurados = [
                    user for user in usuarios 
                    if self.user_manager.usuario_configurado(user['chat_id'])
                ]
                
                if not usuarios_configurados:
                    logger_scan.info("⚠️ Nenhum usuário configurado encontrado")
                    return
                
                logger_scan.info(f"👥 {len(usuarios_configurados)} usuários configurados")
                
                # Coleta bookmakers únicos
                bookmakers_unicos = set()
                for user in usuarios_configurados:
                    user_bookmakers = self.user_manager.get_user_bookmakers(user['chat_id'])
                    bookmakers_unicos.update(user_bookmakers)
                
                if not bookmakers_unicos:
                    logger_scan.info("⚠️ Nenhum bookmaker configurado")
                    return
                
                logger_scan.info(f"📚 {len(bookmakers_unicos)} bookmakers únicos: {list(bookmakers_unicos)}")
                
                # Busca eventos para cada bookmaker
                todos_eventos = []
                for bookmaker in bookmakers_unicos:
                    try:
                        eventos = await self.api_client.get_eventos_geral(bookmaker)
                        todos_eventos.extend(eventos)
                        logger_scan.info(f"📊 {bookmaker}: {len(eventos)} eventos")
                    except Exception as e:
                        logger_scan.error(f"❌ Erro ao buscar eventos para {bookmaker}: {e}")
                        self.stats['erros_api'] += 1
                
                logger_scan.info(f"📈 Total de eventos coletados: {len(todos_eventos)}")
                self.stats['total_eventos'] += len(todos_eventos)
                
                # Processa eventos para cada usuário com momento de scan consistente
                total_alertas = 0
                for user in usuarios_configurados:
                    try:
                        alertas_enviados = await self._processar_usuario(user, todos_eventos, momento_scan)
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
                logger_scan.info(f"✅ Scan concluído em {elapsed:.2f}s - {total_alertas} alertas enviados")
                
                # Atualiza status da API
                self.db.set_api_status(True, "API funcionando normalmente")
                
            except Exception as e:
                logger_scan.error(f"❌ Erro no scan principal: {e}")
                self.db.set_api_status(False, "Erro no scan", str(e))
                self.stats['erros_api'] += 1
    
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
            from filtros import calcular_janela_tempo_dinamica
            janela_tempo = calcular_janela_tempo_dinamica(filtro_dias, momento_scan)
        
        # Filtra eventos válidos
        eventos_validos = []
        for evento in todos_eventos:
            if evento_valido(evento, filtros) and aplicar_filtros_dinamicos(evento, filtros, janela_tempo):
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
                    logger_scan.info(f"🚨 ALERTA INSTANTÂNEO detectado para {chat_id}: EV {ev:.2%}")
                else:
                    alertas_normais.append((evento, stake))
        
        # Envia alertas instantâneos IMEDIATAMENTE
        alertas_enviados = 0
        for evento, stake in alertas_instantaneos:
            try:
                # Import local para evitar circular import
                from bot_ev import enviar_alerta_instantaneo
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
        """Job de limpeza a cada hora"""
        try:
            logger_geral.info("🧹 Iniciando limpeza...")
            
            # Limpa cache antigo
            self.cache.clean_old_cache(30)
            
            # Limpa logs de rate limiting
            self.rate_limiter.clean_old_logs()
            
            logger_geral.info("✅ Limpeza concluída")
            
        except Exception as e:
            logger_geral.error(f"❌ Erro na limpeza: {e}")
    
    async def cleanup_database_job(self):
        """Job de limpeza do banco às 3h da manhã"""
        try:
            logger_geral.info("🗄️ Iniciando limpeza do banco...")
            
            # Limpa cache antigo
            self.cache.clean_old_cache(7)
            
            # Limpa logs de rate limiting antigos
            self.rate_limiter.clean_old_logs()
            
            logger_geral.info("✅ Limpeza do banco concluída")
            
        except Exception as e:
            logger_geral.error(f"❌ Erro na limpeza do banco: {e}")
    
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
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do scheduler"""
        return {
            **self.stats,
            'usuarios_ativos': len(self.user_manager.get_all_users()),
            'api_healthy': self.status.is_api_healthy(),
            'rate_limit_info': self.rate_limiter.get_rate_limit_info()
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
        logger_geral.info(f"🤖 Bot EV+ iniciado (Feed: {FEED_ID})")
        
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
