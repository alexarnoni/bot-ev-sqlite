#!/usr/bin/env python3
"""
Script para iniciar feeds no Windows sem tmux
"""
import os
import sys
import subprocess
import time
import threading
from pathlib import Path

def start_feed(feed_id):
    """Inicia um feed específico"""
    print(f"🚀 Iniciando feed: {feed_id}")
    
    # Define variáveis de ambiente
    env = os.environ.copy()
    env['FEED_ID'] = feed_id
    
    # Inicia o bot listener
    print(f"📱 Iniciando listener para {feed_id}...")
    listener_process = subprocess.Popen(
        [sys.executable, "bot_listener.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Aguarda um pouco
    time.sleep(2)
    
    # Inicia o scheduler
    print(f"⏰ Iniciando scheduler para {feed_id}...")
    scheduler_process = subprocess.Popen(
        [sys.executable, "main_scheduler.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    print(f"✅ Feed {feed_id} iniciado!")
    print(f"   Listener PID: {listener_process.pid}")
    print(f"   Scheduler PID: {scheduler_process.pid}")
    
    return listener_process, scheduler_process

def main():
    print("INICIANDO FEEDS NO WINDOWS")
    print("==========================")
    print()
    
    # Para qualquer processo Python relacionado ao bot
    print("Parando processos existentes...")
    try:
        subprocess.run(["taskkill", "/f", "/im", "python.exe"], 
                      capture_output=True, text=True)
    except:
        pass
    
    time.sleep(3)
    
    # Cria arquivo .env se não existir
    env_content = """# Bot EV+ - Configuração de Ambiente
# Mapeamento correto dos feeds baseado nos bots do Telegram

# ===========================================
# TOKENS DOS BOTS (um por feed)
# ===========================================
# feed_default = Feed principal (@ArnoniBot)
BOT_TOKEN_DEFAULT=7819087759:AAEe2FzOA7R-9Q1X2ENZDDFZpWEzba-NYXI

# feed1 = Feed 1 (@ArnoniFeed1Bot)
BOT_TOKEN_FEED1=8047370953:AAG0sh1sjVqyW7NnmrGqBVJypmRcPYHb9hM

# feed2 = Feed 2 (@ArnoniFeed2Bot)
BOT_TOKEN_FEED2=8435178186:AAGQx2F-i9pNjZ4XXkQvMpazPMwjFiW9HfY

# feed3 = Feed 3 (@ArnoniFeed3Bot)
BOT_TOKEN_FEED3=7812298685:AAHpClDOP4hxGgGXw5H29wyqBJRvfvg5JxM

# feed4 = Feed 4 (@ArnoniFeed4Bot)
BOT_TOKEN_FEED4=8222396387:AAF8G1gljEDZ8DvrH0HQA9s3ogJgw6Lubr8

# feed_test = teste (@ArnonitesteBot)
BOT_TOKEN_FEED_TEST=8419247298:AAGvkg7BkswyEO1xH0MAdZHyzNHZ7OFX4Es

# ===========================================
# API ODDS
# ===========================================
ODDS_API_KEY=d1ffd194fc054b5c7e9691d6aed713c66ab77bc0c9fbd62f66c0d8b04c6f1bea

# ===========================================
# CONFIGURAÇÃO DE FEEDS
# ===========================================
FEEDS=default feed1 feed2 feed3 feed4 feed_test
FEED_ID=default

# ===========================================
# USUÁRIOS ADMINISTRADORES
# ===========================================
ADMIN_USERS=350780046

# ===========================================
# CONFIGURAÇÕES DO SISTEMA
# ===========================================
LOG_LEVEL=INFO
DASHBOARD_PORT=8080
RATE_LIMIT_REQUESTS_PER_HOUR=4800
MAX_CONCURRENT_SCANS=3
CACHE_CLEANUP_DAYS=30
REQUEST_LOG_CLEANUP_HOURS=2
"""
    
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("Arquivo .env criado")
    print()
    
    # Pergunta quais feeds iniciar
    print("Feeds disponíveis:")
    print("1. default (Feed principal - @ArnoniBot)")
    print("2. feed_test (teste - @ArnonitesteBot)")
    print("3. feed1 (Feed 1 - @ArnoniFeed1Bot)")
    print("4. feed2 (Feed 2 - @ArnoniFeed2Bot)")
    print("5. feed3 (Feed 3 - @ArnoniFeed3Bot)")
    print("6. feed4 (Feed 4 - @ArnoniFeed4Bot)")
    print("7. Todos (default + feed_test)")
    print()
    
    choice = input("Escolha uma opção (1-7): ").strip()
    
    feeds_to_start = []
    
    if choice == "1":
        feeds_to_start = ["default"]
    elif choice == "2":
        feeds_to_start = ["feed_test"]
    elif choice == "3":
        feeds_to_start = ["feed1"]
    elif choice == "4":
        feeds_to_start = ["feed2"]
    elif choice == "5":
        feeds_to_start = ["feed3"]
    elif choice == "6":
        feeds_to_start = ["feed4"]
    elif choice == "7":
        feeds_to_start = ["default", "feed_test"]
    else:
        print("Opção inválida")
        return
    
    # Inicia os feeds
    processes = []
    
    for i, feed_id in enumerate(feeds_to_start):
        if i > 0:
            print(f"Aguardando 10 segundos antes de iniciar {feed_id}...")
            time.sleep(10)
        
        listener, scheduler = start_feed(feed_id)
        processes.append((feed_id, listener, scheduler))
    
    print()
    print("FEEDS INICIADOS COM SUCESSO!")
    print("============================")
    print()
    print("Processos ativos:")
    for feed_id, listener, scheduler in processes:
        print(f"• {feed_id}: Listener PID {listener.pid}, Scheduler PID {scheduler.pid}")
    
    print()
    print("Para verificar se está funcionando:")
    print("• Abra o Telegram e teste os bots")
    print("• Verifique os logs em logs/")
    print()
    print("Para parar todos os feeds:")
    print("• Pressione Ctrl+C")
    print("• Ou execute: taskkill /f /im python.exe")
    
    try:
        # Mantém o script rodando
        while True:
            time.sleep(60)
            print(f"{time.strftime('%H:%M:%S')} - Feeds ainda rodando...")
    except KeyboardInterrupt:
        print("\nParando todos os feeds...")
        for feed_id, listener, scheduler in processes:
            try:
                listener.terminate()
                scheduler.terminate()
                print(f"Feed {feed_id} parado")
            except:
                pass
        print("Todos os feeds foram parados")

if __name__ == "__main__":
    main()
