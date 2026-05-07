#!/usr/bin/env python3
"""Entrypoint wrapper - delegates to src.bot.bot_listener"""
import sys
import os

# Ensure project root is in sys.path for src package resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.bot.bot_listener import get_app

if __name__ == "__main__":
    print("🚀 Bot EV+ iniciado!")
    get_app().run_polling()
