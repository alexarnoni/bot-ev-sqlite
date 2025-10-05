#!/usr/bin/env python3
"""
Script para inicializar o banco de dados SQLite com as tabelas necessárias
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime

def init_database():
    """Inicializa o banco de dados com as tabelas necessárias"""
    
    # Caminho do banco
    db_path = Path(os.getenv("BOT_DB_PATH", "bot.sqlite3"))
    
    print(f"🔧 Inicializando banco de dados: {db_path}")
    
    # Conectar ao banco
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Criar tabela users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE NOT NULL,
                nome TEXT,
                username TEXT,
                filter_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Criar tabela alert_history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_date TEXT,
                home_team TEXT,
                away_team TEXT,
                ev_value REAL,
                bookmaker TEXT,
                league TEXT,
                odds REAL,
                stake REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Criar tabela api_cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE NOT NULL,
                cache_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT
            )
        """)
        
        # Criar índices para performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_user_id ON alert_history(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_created_at ON alert_history(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_cache_key ON api_cache(cache_key)")
        
        # Commit das mudanças
        conn.commit()
        
        print("✅ Banco de dados inicializado com sucesso!")
        print("📋 Tabelas criadas:")
        print("   • users - Dados dos usuários")
        print("   • alert_history - Histórico de alertas")
        print("   • api_cache - Cache da API")
        
        # Verificar se há dados
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()["count"]
        print(f"👥 Usuários cadastrados: {user_count}")
        
    except Exception as e:
        print(f"❌ Erro ao inicializar banco: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    init_database()
