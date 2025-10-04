#!/usr/bin/env python3
"""
Teste simples do import do telegram
"""
import sys
import os

print("=== TESTE DE IMPORT TELEGRAM ===")
print(f"Python: {sys.executable}")
print(f"Python path: {sys.path[:3]}...")

try:
    import telegram
    print(f"OK - telegram importado: {telegram.__file__}")
    print(f"OK - telegram path: {telegram.__path__}")
    
    try:
        from telegram import Update
        print("OK - Update importado com sucesso!")
    except ImportError as e:
        print(f"ERRO - Erro ao importar Update: {e}")
        
    try:
        from telegram import InlineKeyboardButton
        print("OK - InlineKeyboardButton importado com sucesso!")
    except ImportError as e:
        print(f"ERRO - Erro ao importar InlineKeyboardButton: {e}")
        
    try:
        from telegram import InlineKeyboardMarkup
        print("OK - InlineKeyboardMarkup importado com sucesso!")
    except ImportError as e:
        print(f"ERRO - Erro ao importar InlineKeyboardMarkup: {e}")
        
except ImportError as e:
    print(f"ERRO - Erro ao importar telegram: {e}")

print("\n=== FIM DO TESTE ===")
