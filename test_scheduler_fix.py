#!/usr/bin/env python3
"""
Teste para verificar se o scheduler funciona com asyncio
"""
import os
import asyncio

# Define FEED_ID para teste
os.environ['FEED_ID'] = 'default'

print("Testando scheduler com asyncio...")

async def test_scheduler():
    try:
        print("1. Importando main_scheduler...")
        from main_scheduler import BotScheduler
        print("OK - Importação")
        
        print("2. Criando scheduler...")
        scheduler = BotScheduler()
        print("OK - Scheduler criado")
        
        print("3. Iniciando scheduler...")
        scheduler.start()
        print("OK - Scheduler iniciado")
        
        print("4. Aguardando 10 segundos...")
        await asyncio.sleep(10)
        
        print("5. Parando scheduler...")
        scheduler.stop()
        print("OK - Scheduler parado")
        
        print("\nTESTE COMPLETO - SCHEDULER FUNCIONA COM ASYNCIO!")
        return True
        
    except Exception as e:
        print(f"\nERRO NO SCHEDULER: {e}")
        print(f"Tipo do erro: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_scheduler())
    if result:
        print("\nSUCESSO: Scheduler funciona corretamente!")
    else:
        print("\nFALHA: Scheduler ainda tem problemas!")
