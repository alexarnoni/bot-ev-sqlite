#!/usr/bin/env python3
"""
Teste simples para verificar se o scheduler consegue iniciar
"""
import os
import sys

# Define FEED_ID para teste
os.environ['FEED_ID'] = 'default'

print("🔍 Testando importações do scheduler...")

try:
    print("1. Testando importações básicas...")
    import asyncio
    import time
    from datetime import datetime
    print("✅ Importações básicas OK")
    
    print("2. Testando APScheduler...")
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    print("✅ APScheduler OK")
    
    print("3. Testando config...")
    from config import MAX_CONCURRENT_SCANS, FEED_ID
    print(f"✅ Config OK - FEED_ID: {FEED_ID}")
    
    print("4. Testando database...")
    from database import get_db
    print("✅ Database OK")
    
    print("5. Testando api_client...")
    from api_client import OddsAPIClient
    print("✅ API Client OK")
    
    print("6. Testando outros módulos...")
    from usuarios import get_user_manager
    from cache import get_cache
    from historico import get_history
    from status import get_status
    from rate_limiter import get_rate_limiter
    print("✅ Módulos auxiliares OK")
    
    print("7. Testando filtros...")
    from filtros import evento_valido, aplicar_filtros_dinamicos
    print("✅ Filtros OK")
    
    print("8. Testando bot_core...")
    from bot_core import definir_stake
    print("✅ Bot Core OK")
    
    print("9. Testando bot_ev...")
    from bot_ev import enviar_alertas_batch
    print("✅ Bot EV OK")
    
    print("10. Testando utils...")
    from utils import logger_geral, logger_scan, update_league_catalog, LIGAS_POR_REGIAO
    print("✅ Utils OK")
    
    print("\n🎉 TODAS AS IMPORTAÇÕES FUNCIONARAM!")
    print("O problema não é nas importações.")
    
except Exception as e:
    print(f"\n❌ ERRO NA IMPORTAÇÃO: {e}")
    print(f"Tipo do erro: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🔧 Testando criação do scheduler...")
try:
    from main_scheduler import BotScheduler
    scheduler = BotScheduler()
    print("✅ Scheduler criado com sucesso!")
    
    print("🔧 Testando inicialização...")
    scheduler.start()
    print("✅ Scheduler iniciado com sucesso!")
    
    print("⏳ Aguardando 5 segundos...")
    import time
    time.sleep(5)
    
    print("🛑 Parando scheduler...")
    scheduler.stop()
    print("✅ Scheduler parado com sucesso!")
    
    print("\n🎉 TESTE COMPLETO - SCHEDULER FUNCIONA!")
    
except Exception as e:
    print(f"\n❌ ERRO NO SCHEDULER: {e}")
    print(f"Tipo do erro: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
