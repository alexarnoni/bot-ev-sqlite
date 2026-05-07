#!/usr/bin/env python3
"""Entrypoint wrapper - delegates to src.core.database"""
import sys
import os

# Ensure project root is in sys.path for src package resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.database import get_db
from src.core.config import get_database_path


def init_database():
    db = get_db()
    # Apenas instanciar já cria as tabelas via _init_db()
    db_path = get_database_path()
    print(f"✅ Banco inicializado no caminho: {db_path}")


if __name__ == "__main__":
    init_database()
