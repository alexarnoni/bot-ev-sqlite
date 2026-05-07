"""
Scanner Global Único - Processo dedicado para scan automático
Executa 1 scan a cada 2 minutos e salva em cache global para todos os feeds
"""
import asyncio
import time
import os
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from src.core.config import FEED_ID, FEEDS
from src.core.database import Database
from src.api.api_client import OddsAPIClient
from src.api.rate_limiter_global import get_global_rate_limiter
from src.utils.utils import logger_geral, logger_scan, update_league_catalog, LIGAS_POR_REGIAO
from src.core.logging_config import get_logger
from src.utils.metrics import record_scan_duration, measure_time, get_metrics_summary, save_metrics
from src.scanner.scan_cache import get_snapshot_cache

# Logger específico para scanner global
logger = get_logger("global_scanner")

class GlobalScanner:
    def __init__(self):
        # Usa o event loop atual para jobs assíncronos
        self.scheduler = AsyncIOScheduler(event_loop=asyncio.get_event_loop())
        self.api_client = OddsAPIClient()
        self.global_rl = get_global_rate_limiter()
        self.snapshot_cache = get_snapshot_cache()
        
        # Estatísticas
        self.stats = {
            'total_scans': 0,
            'total_eventos': 0,
            'ultimo_scan': None,
            'erros_api': 0
        }
    
    def start(self):
        """Inicia o scanner global"""
        logger.info("🌍 Iniciando Scanner Global Único...")
        
        # JOB PRINCIPAL: SCAN GLOBAL A CADA 2 MINUTOS
        self.scheduler.add_job(
            self.global_scan_job,
            IntervalTrigger(minutes=2),  # ← SEMPRE 2 MINUTOS
            id='global_scan',
            max_instances=1,
            replace_existing=True
        )
        
        # Limpeza do cache global a cada hora
        self.scheduler.add_job(
            self.cleanup_job,
            CronTrigger(minute=0),
            id='cleanup_global'
        )
        
        # Estatísticas a cada 30 minutos
        self.scheduler.add_job(
            self.stats_job,
            IntervalTrigger(minutes=30),
            id='stats_global'
        )
        
        # Inicia o scheduler
        self.scheduler.start()
        logger.info("✅ Scanner Global iniciado (scan único a cada 2min)")
        
        # Log dos jobs ativos
        for job in self.scheduler.get_jobs():
            logger.info(f"📅 Job global ativo: {job.id} - {job.trigger}")
    
    @measure_time('global_scan')
    async def global_scan_job(self):
        """Job principal de scan global - executa a cada 2 minutos"""
        try:
            logger.info("🌍 Iniciando scan global único...")
            start_time = time.time()
            
            # Calcula momento do scan uma vez para consistência
            momento_scan = datetime.now(timezone.utc)
            
            # Verifica rate limit GLOBAL
            if not self.global_rl.can_make_request():
                logger.warning("⚠️ Rate limit global atingido, pulando scan")
                return
            
            # Busca TODOS os usuários de TODOS os feeds configurados
            usuarios_todos_feeds = await self._buscar_usuarios_todos_feeds()
            if not usuarios_todos_feeds:
                logger.info("⚠️ Nenhum usuário encontrado em todos os feeds")
                return
            
            logger.info(f"👥 {len(usuarios_todos_feeds)} usuários encontrados em todos os feeds")
            
            # Coleta bookmakers únicos de TODOS os feeds
            bookmakers_unicos = set()
            for user in usuarios_todos_feeds:
                feed_db = Database(user['feed_id'])
                user_bookmakers = feed_db.get_user_bookmakers(user['chat_id'])
                bookmakers_unicos.update(user_bookmakers)
            
            if not bookmakers_unicos:
                logger.info("⚠️ Nenhum bookmaker configurado em todos os feeds")
                return
            
            logger.info(f"📚 {len(bookmakers_unicos)} bookmakers únicos: {list(bookmakers_unicos)}")
            
            # Busca eventos em lote usando TODOS os bookmakers únicos
            todos_eventos = []
            try:
                lista_bookmakers = sorted(list(bookmakers_unicos))
                logger.info(
                    f"🔗 Buscando eventos em lote para {len(lista_bookmakers)} bookmakers (1 request global): {lista_bookmakers}"
                )
                todos_eventos = await self.api_client.get_value_bets(lista_bookmakers)
                # Registra requisições no rate limiter global (1 por bookmaker)
                for _ in lista_bookmakers:
                    self.global_rl.log_request(endpoint='/value-bets', api_key=self.api_client.api_key[:8])
            except Exception as e:
                logger.error(f"❌ Erro ao buscar eventos em lote global: {e}")
                self.stats['erros_api'] += 1
                return
            
            logger.info(f"📈 Total de eventos coletados (scan global): {len(todos_eventos)}")
            self.stats['total_eventos'] += len(todos_eventos)
            
            # Salva snapshot GLOBAL para todos os feeds usarem
            try:
                await self._salvar_snapshot_global(todos_eventos, lista_bookmakers, momento_scan)
                logger.info("💾 Snapshot global salvo para todos os feeds")
            except Exception as e:
                logger.error(f"❌ Falha ao salvar snapshot global: {e}")
            
            # Atualiza estatísticas
            self.stats['total_scans'] += 1
            self.stats['ultimo_scan'] = datetime.now()
            
            # Atualiza catálogo de ligas
            update_league_catalog(LIGAS_POR_REGIAO)
            
            # Log final
            elapsed = time.time() - start_time
            logger.info(f"✅ Scan global concluído em {elapsed:.2f}s - {len(todos_eventos)} eventos para todos os feeds")
            
            # Registra métricas do scan
            record_scan_duration(elapsed, len(todos_eventos), 0)  # 0 alerts pois só coleta dados
            
        except Exception as e:
            logger.error(f"❌ Erro no scan global: {e}")
            self.stats['erros_api'] += 1
    
    async def _buscar_usuarios_todos_feeds(self):
        """Busca usuários de todos os feeds configurados"""
        usuarios_todos_feeds = []
        
        # Lista de feeds para buscar usuários (sempre inclui default)
        feeds = set(["default"] + FEEDS + ["feed_test"])
        
        for feed_id in sorted(feeds):
            try:
                feed_db = Database(feed_id)
                users = feed_db.get_all_users()
                usuarios_configurados = [
                    user for user in users 
                    if feed_db.usuario_configurado(user['chat_id'])
                ]
                
                # Adiciona feed_id ao usuário para identificação
                for user in usuarios_configurados:
                    user['feed_id'] = feed_id
                
                usuarios_todos_feeds.extend(usuarios_configurados)
                logger.info(f"📱 Feed {feed_id}: {len(usuarios_configurados)} usuários configurados")
                    
            except Exception as e:
                logger.warning(f"⚠️ Erro ao buscar usuários do feed {feed_id}: {e}")
                continue
        
        return usuarios_todos_feeds
    
    async def _salvar_snapshot_global(self, eventos, bookmakers, timestamp):
        """Salva snapshot global usando DB global"""
        try:
            # Usa cache global compartilhado (mesma estrutura consumida pelos feeds)
            self.snapshot_cache.set_snapshot(eventos, bookmakers, timestamp)
        except Exception as e:
            logger.error(f"❌ Erro ao salvar snapshot global: {e}")
            raise
    
    async def cleanup_job(self):
        """Job de limpeza do cache global"""
        try:
            logger.info("🧹 Iniciando limpeza do cache global...")
            
            # Limpa cache global antigo (> 1 hora)
            with self.snapshot_cache.get_connection() as conn:
                conn.execute("""
                    DELETE FROM api_cache 
                    WHERE created_at < datetime('now', '-1 hour')
                """)
            
            logger.info("✅ Limpeza do cache global concluída")
            
        except Exception as e:
            logger.error(f"❌ Erro na limpeza do cache global: {e}")
    
    async def stats_job(self):
        """Job de estatísticas do scanner global"""
        try:
            logger.info("📊 Estatísticas do Scanner Global:")
            logger.info(f"   Total de scans: {self.stats['total_scans']}")
            logger.info(f"   Total de eventos: {self.stats['total_eventos']}")
            logger.info(f"   Último scan: {self.stats['ultimo_scan']}")
            logger.info(f"   Erros API: {self.stats['erros_api']}")
            
            # Salva métricas detalhadas
            metrics_summary = get_metrics_summary()
            logger.info("📈 Métricas de Performance:")
            
            # Mostra percentis de latência
            if 'latency_metrics' in metrics_summary:
                for category, metrics in metrics_summary['latency_metrics'].items():
                    if metrics.get('percentiles'):
                        p50 = metrics['percentiles'].get('p50', 0)
                        p95 = metrics['percentiles'].get('p95', 0)
                        p99 = metrics['percentiles'].get('p99', 0)
                        logger.info(f"   {category}: P50={p50:.3f}s, P95={p95:.3f}s, P99={p99:.3f}s")
            
            # Salva métricas em arquivo
            save_metrics(f"logs/metrics_global_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            
        except Exception as e:
            logger.error(f"❌ Erro ao coletar estatísticas: {e}")
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do scanner global"""
        return self.stats
    
    def stop(self):
        """Para o scanner global"""
        self.scheduler.shutdown()
        logger.info("🛑 Scanner Global parado")

# Função principal para executar o scanner global
async def main():
    """Função principal do scanner global"""
    scanner = GlobalScanner()
    
    try:
        scanner.start()
        logger.info("🌍 Scanner Global Único iniciado")
        
        # Mantém o scanner rodando
        while True:
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("🛑 Interrompido pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
    finally:
        scanner.stop()

if __name__ == "__main__":
    asyncio.run(main())
