#!/usr/bin/env python3
"""
Script para validar identificadores de esportes americanos na API Odds
"""
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Identificadores que vamos testar
AMERICAN_SPORTS_TO_TEST = {
    'NFL': 'americanfootball_nfl',
    'College Football': 'americanfootball_ncaaf', 
    'NBA': 'basketball_nba',
    'WNBA': 'basketball_wnba',
    'MLB': 'baseball_mlb',
    'Minor League Baseball': 'baseball_milb',
    'MLS': 'soccer_usa_mls',
    'USL Championship': 'soccer_usa_usl'
}

async def test_sport_identifiers():
    """Testa se os identificadores de esportes americanos estão corretos"""
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        print("ERRO: ODDS_API_KEY não encontrada no .env")
        return False
    
    print("Testando identificadores de esportes americanos...")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        for sport_name, sport_slug in AMERICAN_SPORTS_TO_TEST.items():
            print(f"\nTestando {sport_name} ({sport_slug})...")
            
            try:
                # Testa endpoint de eventos
                url = f"https://api.odds-api.io/v3/events"
                params = {
                    'apiKey': api_key,
                    'sport': sport_slug,
                    'status': 'pending',
                    'limit': 5
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        events = data if isinstance(data, list) else data.get('data', [])
                        
                        if events:
                            print(f"  OK: {len(events)} eventos encontrados")
                            
                            # Mostra alguns exemplos
                            for i, event in enumerate(events[:2]):
                                print(f"    {i+1}. {event.get('home', 'N/A')} vs {event.get('away', 'N/A')}")
                                print(f"       Liga: {event.get('league', {}).get('name', 'N/A')}")
                                print(f"       Data: {event.get('date', 'N/A')}")
                        else:
                            print(f"  AVISO: Nenhum evento ativo no momento")
                    else:
                        error_text = await response.text()
                        print(f"  ERRO {response.status}: {error_text}")
                        
            except Exception as e:
                print(f"  ERRO ao testar {sport_name}: {e}")
    
    return True

async def test_player_props():
    """Testa se conseguimos encontrar player props"""
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        return False
    
    print("\nTestando Player Props...")
    print("=" * 60)
    
    # Testa NBA (mais provável ter props)
    async with aiohttp.ClientSession() as session:
        try:
            # Busca eventos da NBA
            url = f"https://api.odds-api.io/v3/events"
            params = {
                'apiKey': api_key,
                'sport': 'basketball_nba',
                'status': 'pending',
                'limit': 3
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    events = data if isinstance(data, list) else data.get('data', [])
                    
                    if events:
                        # Testa odds de um evento específico
                        event_id = events[0]['id']
                        print(f"Testando props para evento {event_id}...")
                        
                        # Busca odds com bookmakers que oferecem props
                        bookmakers = 'BetMGM,Betano,Bet365'
                        odds_url = f"https://api.odds-api.io/v3/odds"
                        odds_params = {
                            'apiKey': api_key,
                            'eventId': event_id,
                            'bookmakers': bookmakers
                        }
                        
                        async with session.get(odds_url, params=odds_params) as odds_response:
                            if odds_response.status == 200:
                                odds_data = await odds_response.json()
                                
                                # Procura por props
                                props_found = False
                                for bookmaker, markets in odds_data.get('bookmakers', {}).items():
                                    for market in markets:
                                        if 'Props' in market.get('name', '') or 'label' in str(market):
                                            props_found = True
                                            print(f"  OK: Props encontrados em {bookmaker}: {market.get('name', 'N/A')}")
                                            
                                            # Mostra alguns exemplos
                                            for odds in market.get('odds', [])[:2]:
                                                if 'label' in odds:
                                                    print(f"    {odds.get('label', 'N/A')} - {odds.get('hdp', 'N/A')}")
                                            
                                            break
                                    if props_found:
                                        break
                                
                                if not props_found:
                                    print(f"  AVISO: Nenhum player prop encontrado para este evento")
                            else:
                                print(f"  ERRO ao buscar odds: {odds_response.status}")
                    else:
                        print(f"  AVISO: Nenhum evento da NBA encontrado")
                else:
                    print(f"  ERRO ao buscar eventos: {response.status}")
                    
        except Exception as e:
            print(f"  ERRO ao testar player props: {e}")
    
    return True

async def main():
    """Executa todos os testes"""
    print("Iniciando validacao de esportes americanos...")
    print("=" * 60)
    
    # Testa identificadores de esportes
    await test_sport_identifiers()
    
    # Testa player props
    await test_player_props()
    
    print("\nValidacao concluida!")
    print("\nProximos passos:")
    print("1. Verificar se os identificadores estao corretos")
    print("2. Ajustar american_sports_config.py se necessario")
    print("3. Continuar com a implementacao")

if __name__ == "__main__":
    asyncio.run(main())