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
        
        # Criar tabela user_bookmakers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_bookmakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                bookmaker TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        """)
        
        # Criar tabela user_filters
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_filters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE NOT NULL,
                ev_faixa_min REAL,
                ev_faixa_max REAL,
                filtro_dias INTEGER,
                data_inicio TEXT,
                data_fim TEXT,
                horario_inicio TEXT,
                horario_fim TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        """)
        
        # Criar tabela user_leagues
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_leagues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                league TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        """)
        
        # Criar tabela user_sports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                sport TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        """)
        
        # Criar tabela alert_cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                alert_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
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
        
        # Criar tabela pending_alerts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                evento TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        """)
        
        # Criar tabela league_catalog
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS league_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT NOT NULL,
                sport TEXT NOT NULL,
                league TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(region, sport, league)
            )
        """)
        
        # Criar tabela system_status
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_status (
                id INTEGER PRIMARY KEY,
                last_scan TEXT,
                last_alert TEXT,
                api_status TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Criar tabela rate_limiter
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limiter (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_timestamp TEXT NOT NULL
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_bookmakers_chat_id ON user_bookmakers(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_filters_chat_id ON user_filters(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_leagues_chat_id ON user_leagues(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sports_chat_id ON user_sports(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_cache_chat_id ON alert_cache(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_user_id ON alert_history(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_created_at ON alert_history(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_alerts_chat_id ON pending_alerts(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_league_catalog_region_sport ON league_catalog(region, sport)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rate_limiter_timestamp ON rate_limiter(request_timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_cache_key ON api_cache(cache_key)")
        
        # Commit das mudanças
        conn.commit()
        
        print("✅ Banco de dados inicializado com sucesso!")
        print("📋 Tabelas criadas:")
        print("   • users - Dados dos usuários")
        print("   • user_bookmakers - Bookmakers por usuário")
        print("   • user_filters - Filtros por usuário")
        print("   • user_leagues - Ligas por usuário")
        print("   • user_sports - Esportes por usuário")
        print("   • alert_cache - Cache de alertas")
        print("   • alert_history - Histórico de alertas")
        print("   • pending_alerts - Alertas pendentes")
        print("   • league_catalog - Catálogo de ligas")
        print("   • system_status - Status do sistema")
        print("   • rate_limiter - Controle de rate limiting")
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
