#!/usr/bin/env python3
"""
Inicializa o banco no schema normalizado usando Database (bot.db via feed_path).
"""
from database import get_db
from config import get_database_path

def init_database():
    db = get_db()
    # Apenas instanciar já cria as tabelas via _init_db()
    db_path = get_database_path()
    print(f"✅ Banco inicializado no caminho: {db_path}")

if __name__ == "__main__":
    init_database()
