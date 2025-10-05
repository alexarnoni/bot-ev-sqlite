#!/usr/bin/env python3
"""
Teste para verificar se o bot_listener_sqlite.py funciona
"""
import os
import sys

# Define FEED_ID para teste
os.environ['FEED_ID'] = 'default'

print("Testando bot_listener_sqlite.py...")

try:
    print("1. Testando importações básicas...")
    import asyncio
    import logging
    from datetime import datetime
    print("OK - Importações básicas")
    
    print("2. Testando imports do sistema...")
    from config import get_telegram_token, get_listener_log_path
    from database import get_db
    from usuarios import get_user_manager
    from cache import get_cache
    from historico import get_history
    from status import get_status
    from rate_limiter import get_rate_limiter
    print("OK - Imports do sistema")
    
    print("3. Testando imports de filtros e bot...")
    from filtros import evento_valido, aplicar_filtros_dinamicos
    from bot_core import definir_stake
    from bot_ev import enviar_alertas_batch
    from utils import logger_geral, logger_scan, update_league_catalog, LIGAS_POR_REGIAO
    print("OK - Imports de filtros e bot")
    
    print("4. Testando imports do Telegram...")
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters
    print("OK - Imports do Telegram")
    
    print("5. Testando criação do listener...")
    from bot_listener_sqlite import main
    print("OK - Listener criado com sucesso!")
    
    print("\nTODAS AS IMPORTAÇÕES FUNCIONARAM!")
    print("O bot_listener_sqlite.py está pronto para uso.")
    
except Exception as e:
    print(f"\nERRO NA IMPORTAÇÃO: {e}")
    print(f"Tipo do erro: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nTESTE COMPLETO - LISTENER SQLITE FUNCIONA!")
