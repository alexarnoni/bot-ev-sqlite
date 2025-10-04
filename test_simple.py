#!/usr/bin/env python3
"""
Teste simples para verificar se o scheduler consegue iniciar
"""
import os
import sys

# Define FEED_ID para teste
os.environ['FEED_ID'] = 'default'

print("Testando importações do scheduler...")

try:
    print("1. Testando importações básicas...")
    import asyncio
    import time
    from datetime import datetime
    print("OK - Importações básicas")
    
    print("2. Testando APScheduler...")
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    print("OK - APScheduler")
    
    print("3. Testando config...")
    from config import MAX_CONCURRENT_SCANS, FEED_ID
    print(f"OK - Config - FEED_ID: {FEED_ID}")
    
    print("4. Testando database...")
    from database import get_db
    print("OK - Database")
    
    print("5. Testando api_client...")
    from api_client import OddsAPIClient
    print("OK - API Client")
    
    print("6. Testando outros módulos...")
    from usuarios import get_user_manager
    from cache import get_cache
    from historico import get_history
    from status import get_status
    from rate_limiter import get_rate_limiter
    print("OK - Módulos auxiliares")
    
    print("7. Testando filtros...")
    from filtros import evento_valido, aplicar_filtros_dinamicos
    print("OK - Filtros")
    
    print("8. Testando bot_core...")
    from bot_core import definir_stake
    print("OK - Bot Core")
    
    print("9. Testando bot_ev...")
    from bot_ev import enviar_alertas_batch
    print("OK - Bot EV")
    
    print("10. Testando utils...")
    from utils import logger_geral, logger_scan, update_league_catalog, LIGAS_POR_REGIAO
    print("OK - Utils")
    
    print("\nTODAS AS IMPORTAÇÕES FUNCIONARAM!")
    print("O problema não é nas importações.")
    
except Exception as e:
    print(f"\nERRO NA IMPORTAÇÃO: {e}")
    print(f"Tipo do erro: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nTestando criação do scheduler...")
try:
    from main_scheduler import BotScheduler
    scheduler = BotScheduler()
    print("OK - Scheduler criado com sucesso!")
    
    print("Testando inicialização...")
    scheduler.start()
    print("OK - Scheduler iniciado com sucesso!")
    
    print("Aguardando 5 segundos...")
    import time
    time.sleep(5)
    
    print("Parando scheduler...")
    scheduler.stop()
    print("OK - Scheduler parado com sucesso!")
    
    print("\nTESTE COMPLETO - SCHEDULER FUNCIONA!")
    
except Exception as e:
    print(f"\nERRO NO SCHEDULER: {e}")
    print(f"Tipo do erro: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
