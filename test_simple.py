"""
Teste simples do sistema SQLite
"""
import asyncio
import os
import sys
from pathlib import Path

# Adiciona o diretório atual ao path
sys.path.insert(0, str(Path(__file__).parent))

async def test_database():
    """Testa banco de dados"""
    try:
        from database import SQLiteConnectionPool, SQLiteConnectionConfig
        
        def get_database_path():
            feed_id = os.getenv("FEED_ID", "default")
            return os.path.join(os.getcwd(), "data", feed_id, "bot.db")
        
        db_config = SQLiteConnectionConfig(
            database_path=get_database_path(),
            max_connections=10,
            timeout=30.0
        )
        db_pool = SQLiteConnectionPool(db_config)
        
        async with db_pool.get_connection() as conn:
            cursor = await conn.execute("SELECT 1 as test")
            result = await cursor.fetchone()
            print(f"OK - Banco: {result['test']}")
            
        return True
        
    except Exception as e:
        print(f"ERRO - Banco: {e}")
        return False

async def test_config():
    """Testa configuração"""
    try:
        from config import FEED_ID, get_telegram_token
        import os
        
        print(f"OK - Feed ID: {FEED_ID}")
        token = get_telegram_token()
        print(f"OK - Token: {'Sim' if token else 'Não'}")
        if token:
            print(f"OK - Token valido: {token[:10]}...")
        
        return True
        
    except Exception as e:
        print(f"ERRO - Config: {e}")
        return False

async def test_bot_core():
    """Testa bot core"""
    try:
        from bot_core import calcular_ev, definir_stake
        
        ev = calcular_ev({'expectedValue': 105.5})
        stake = definir_stake(0.05, 2.5)
        
        print(f"OK - EV: {ev}")
        print(f"OK - Stake: {stake}")
        
        return True
        
    except Exception as e:
        print(f"ERRO - Bot Core: {e}")
        return False

async def main():
    """Executa testes"""
    print("Testando sistema...\n")
    
    tests = [
        ("Configuracao", test_config),
        ("Banco de Dados", test_database),
        ("Bot Core", test_bot_core),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Testando {test_name}...")
        try:
            result = await test_func()
            if result:
                passed += 1
            print()
        except Exception as e:
            print(f"ERRO inesperado em {test_name}: {e}\n")
    
    print("RESULTADO:")
    print(f"Total: {passed}/{total} testes passaram")
    
    if passed == total:
        print("Sistema OK!")
    else:
        print("Alguns testes falharam.")

if __name__ == "__main__":
    asyncio.run(main())
