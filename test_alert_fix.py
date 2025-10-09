#!/usr/bin/env python3
"""
Test script to verify the NFL alert formatting fix
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from formatadores import montar_nome_mercado

def test_nfl_reception_alert():
    """Test NFL reception alert formatting"""
    
    # Test case 1: Over 1.5 receptions
    evento_over = {
        "market": {
            "name": "player props - beaux collins (receptions)"
        },
        "betSide": "over",
        "event": {
            "sport": "americanfootball"
        },
        "hdp": 1.5
    }
    
    # Test case 2: Under 1.5 receptions  
    evento_under = {
        "market": {
            "name": "player props - beaux collins (receptions)"
        },
        "betSide": "under", 
        "event": {
            "sport": "americanfootball"
        },
        "hdp": 1.5
    }
    
    # Test case 3: Using bet_side field instead of betSide
    evento_bet_side = {
        "market": {
            "name": "player props - beaux collins (receptions)"
        },
        "bet_side": "over",
        "event": {
            "sport": "americanfootball"
        },
        "hdp": 1.5
    }
    
    print("Testing NFL reception alert formatting...")
    print()
    
    print("Test 1 - Over 1.5 receptions (betSide='over'):")
    result1 = montar_nome_mercado(evento_over)
    print(f"Result: {result1}")
    print(f"Expected: Beaux Collins - Mais de 1.5 Recepções")
    print(f"✓ Correct" if "Mais de 1.5 Recepções" in result1 else "✗ Incorrect")
    print()
    
    print("Test 2 - Under 1.5 receptions (betSide='under'):")
    result2 = montar_nome_mercado(evento_under)
    print(f"Result: {result2}")
    print(f"Expected: Beaux Collins - Menos de 1.5 Recepções")
    print(f"✓ Correct" if "Menos de 1.5 Recepções" in result2 else "✗ Incorrect")
    print()
    
    print("Test 3 - Over 1.5 receptions (bet_side='over'):")
    result3 = montar_nome_mercado(evento_bet_side)
    print(f"Result: {result3}")
    print(f"Expected: Beaux Collins - Mais de 1.5 Recepções")
    print(f"✓ Correct" if "Mais de 1.5 Recepções" in result3 else "✗ Incorrect")
    print()
    
    # Test with different player and stat
    evento_different = {
        "market": {
            "name": "player props - cooper kupp (receiving yards)"
        },
        "betSide": "over",
        "event": {
            "sport": "americanfootball"
        },
        "hdp": 75.5
    }
    
    print("Test 4 - Different player and stat:")
    result4 = montar_nome_mercado(evento_different)
    print(f"Result: {result4}")
    print(f"Expected: Cooper Kupp - Mais de 75.5 Jardas de Recepção")
    print(f"✓ Correct" if "Mais de 75.5 Jardas de Recepção" in result4 else "✗ Incorrect")
    print()

if __name__ == "__main__":
    test_nfl_reception_alert()