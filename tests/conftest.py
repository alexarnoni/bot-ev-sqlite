"""Fixtures compartilhadas para testes do bet tracking system."""
import sys
import os
import types
import sqlite3
import pytest
from contextlib import contextmanager

# Configura env vars antes de qualquer import do projeto
os.environ.setdefault('ODDS_API_KEY', 'test_key')
os.environ.setdefault('BOT_TOKEN', 'test_token')
os.environ.setdefault('FEED_ID', 'test_feed')

# Mock aiosqlite para evitar ImportError
aiosqlite_mock = types.ModuleType('aiosqlite')
aiosqlite_mock.Row = None
aiosqlite_mock.connect = None
sys.modules.setdefault('aiosqlite', aiosqlite_mock)

# Adiciona raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class InMemoryDB:
    """Banco SQLite em memória para testes."""

    def __init__(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bets_placed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_hash TEXT NOT NULL UNIQUE,
                chat_id TEXT NOT NULL,
                feed_id TEXT NOT NULL,
                home TEXT,
                away TEXT,
                league TEXT,
                sport TEXT,
                market_type TEXT,
                bet_side TEXT,
                bookmaker TEXT,
                odd_alerta REAL,
                ev_alerta REAL,
                commence_time TEXT,
                commence_time_ajustado TEXT DEFAULT NULL,
                valor_apostado REAL DEFAULT NULL,
                status TEXT DEFAULT 'pendente'
                    CHECK(status IN ('pendente','ganhou','perdeu','empate','cashout','pulei','expirado')),
                valor_cashout REAL DEFAULT NULL,
                lucro REAL DEFAULT NULL,
                tentativas_lembrete INTEGER DEFAULT 0,
                timestamp_alerta TEXT,
                timestamp_apostou TEXT,
                timestamp_resultado TEXT,
                timestamp_lembrete_enviado TEXT
            )
        """)
        self.conn.commit()

    @contextmanager
    def get_connection(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise


@pytest.fixture
def db():
    """Retorna banco em memória limpo para cada teste."""
    return InMemoryDB()


@pytest.fixture
def tracker(db):
    """Retorna instância de BetsTracker com banco em memória."""
    from bets_tracker import BetsTracker
    return BetsTracker(db)


@pytest.fixture
def sample_dados():
    """Dados de alerta de exemplo."""
    return {
        'home': 'TeamA',
        'away': 'TeamB',
        'league': 'Premier League',
        'sport': 'soccer',
        'market_type': 'h2h',
        'bet_side': 'home',
        'bookmaker': 'Bet365',
        'odd_alerta': 2.0,
        'ev_alerta': 0.05,
        'commence_time': '2025-06-01 15:00:00',
    }
