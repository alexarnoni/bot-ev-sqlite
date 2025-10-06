import asyncio
import aiohttp
import os
import json
from dotenv import load_dotenv

load_dotenv()

async def test():
    api_key = os.getenv("ODDS_API_KEY")
    
    url = "https://api.odds-api.io/v3/value-bets"
    params = {
        'apiKey': api_key,
        'bookmaker': 'Bet365'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            print(f"Status: {response.status}")
            
            if response.status == 200:
                data = await response.json()
                print(f"\nTotal items: {len(data)}\n")
                
                # Mostra estrutura completa do primeiro item
                if data:
                    print("ESTRUTURA DO PRIMEIRO ITEM:")
                    print(json.dumps(data[0], indent=2))
                    
                    # Se tiver evento aninhado
                    if 'event' in data[0]:
                        print("\n\nESTRUTURA DO EVENT:")
                        print(json.dumps(data[0]['event'], indent=2))

asyncio.run(test())