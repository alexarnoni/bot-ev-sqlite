#!/usr/bin/env python3
"""
Script para diagnosticar problemas com os listeners
"""

import os
import subprocess
import sys
from pathlib import Path

def check_tmux_sessions():
    """Verifica sessões tmux ativas"""
    try:
        result = subprocess.run(['tmux', 'list-sessions'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("📊 Sessões tmux ativas:")
            print(result.stdout)
        else:
            print("❌ Nenhuma sessão tmux encontrada")
    except Exception as e:
        print(f"❌ Erro ao verificar tmux: {e}")

def check_logs():
    """Verifica logs dos listeners"""
    feeds = ['default', 'feed1', 'feed2', 'feed3', 'feed4', 'feed_test']
    
    for feed in feeds:
        log_file = f"logs/listener_{feed}.log"
        print(f"\n🔸 Feed: {feed}")
        
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        print("📄 Últimas 3 linhas do log:")
                        for line in lines[-3:]:
                            print(f"  {line.strip()}")
                    else:
                        print("📄 Log vazio")
            except Exception as e:
                print(f"❌ Erro ao ler log: {e}")
        else:
            print(f"❌ Log não encontrado: {log_file}")

def check_processes():
    """Verifica processos Python relacionados aos listeners"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            bot_processes = [line for line in lines if 'bot_listener.py' in line]
            
            if bot_processes:
                print("\n🐍 Processos bot_listener.py encontrados:")
                for process in bot_processes:
                    print(f"  {process}")
            else:
                print("\n❌ Nenhum processo bot_listener.py encontrado")
        else:
            print("❌ Erro ao verificar processos")
    except Exception as e:
        print(f"❌ Erro ao verificar processos: {e}")

def main():
    print("🔍 DIAGNÓSTICO DOS LISTENERS")
    print("=" * 40)
    
    check_tmux_sessions()
    check_logs()
    check_processes()
    
    print("\n🔧 Comandos para resolver:")
    print("1. Parar todos: ./stop_all_feeds.sh")
    print("2. Iniciar todos: ./start_all_feeds.sh")
    print("3. Verificar logs: tail -f logs/listener_default.log")

if __name__ == "__main__":
    main()
