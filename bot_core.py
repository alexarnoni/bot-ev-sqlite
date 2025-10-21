"""
Módulo core do Bot EV+ - Conversão de EV e cálculos
"""
def calcular_ev(evento):
    """
    API já retorna EV calculado no campo expectedValue
    Formato API: 100.84 significa 100.84%
    Conversão: (100.84 / 100) - 1 = 0.0084 (0.84%)
    """
    try:
        expected_value = evento.get('expectedValue', 0)
        # Converte de % para decimal: 100.84 → 0.0084
        return (expected_value / 100) - 1
    except Exception as e:
        print(f"Erro ao converter EV: {e}")
        return 0

def obter_probabilidade_real(odd_pinnacle):
    """Mantido para compatibilidade, mas não usado no fluxo principal"""
    return 1 / odd_pinnacle if odd_pinnacle > 0 else 0

def calcular_odd_minima(ev, prob_real):
    """Calcula a odd mínima para manter o mesmo EV do alerta."""
    try:
        return (ev + 1) / prob_real if prob_real > 0 else None
    except Exception:
        return None

def definir_stake(ev, odd):
    """
    Define stake fixa com base apenas na odd:
    - Odds entre 1.50 e 3.50 → 1.0u
    - Odds entre 3.51 e 8.00 → 0.5u
    - Odds acima de 8.00     → 0.25u
    - Odds fora desses intervalos → 0.1u
    
    IMPORTANTE: A validação de EV já foi feita pelos filtros do usuário.
    Não validamos EV aqui porque cada usuário tem seu próprio ev_minimo configurado.
    """
    try:
        odd = float(odd)
    except (TypeError, ValueError):
        return 0

    if 1.50 <= odd <= 3.50:
        return 1.0
    elif 3.51 <= odd <= 8.00:
        return 0.5
    elif odd > 8.00:
        return 0.25
    else:
        return 0.1

def calcular_ev_player_prop(prop_data: dict) -> dict:
    """
    Calcula EV para player props comparando odds entre casas
    
    Args:
        prop_data: Dicionário com estrutura:
            {
                'bookmaker_odds': {
                    'Bet365': {'over': 1.95, 'under': 1.85},
                    'BetMGM': {'over': 2.00, 'under': 1.80},
                    ...
                }
            }
    
    Returns:
        Dicionário com EV por casa e lado (over/under):
        {
            'Bet365': {'over': 0.025, 'under': -0.015, 'best': 'over', 'best_ev': 0.025, 'best_odds': 1.95},
            'BetMGM': {'over': 0.050, 'under': -0.020, 'best': 'over', 'best_ev': 0.050, 'best_odds': 2.00},
            ...
        }
    """
    try:
        bookmaker_odds = prop_data.get('bookmaker_odds', {})
        
        if not bookmaker_odds:
            return {}
        
        # Coletar todas as odds (over e under) para calcular "fair odds"
        all_over_odds = []
        all_under_odds = []
        
        for bookmaker, odds in bookmaker_odds.items():
            over = odds.get('over')
            under = odds.get('under')
            
            if over and over > 1.0:
                all_over_odds.append(over)
            if under and under > 1.0:
                all_under_odds.append(under)
        
        if not all_over_odds or not all_under_odds:
            return {}
        
        # Usar a menor odd como "fair odds" (similar ao Pinnacle)
        # Odds mais baixas geralmente indicam maior probabilidade verdadeira
        fair_over = min(all_over_odds)
        fair_under = min(all_under_odds)
        
        # Calcular EV para cada casa
        ev_results = {}
        
        for bookmaker, odds in bookmaker_odds.items():
            over_odds = odds.get('over')
            under_odds = odds.get('under')
            
            ev_over = None
            ev_under = None
            
            # Calcular EV para over
            if over_odds and over_odds > 1.0:
                ev_over = (over_odds / fair_over) - 1
            
            # Calcular EV para under
            if under_odds and under_odds > 1.0:
                ev_under = (under_odds / fair_under) - 1
            
            # Determinar melhor lado (over ou under)
            if ev_over is not None and ev_under is not None:
                if ev_over > ev_under:
                    best_side = 'over'
                    best_ev = ev_over
                    best_odds = over_odds
                else:
                    best_side = 'under'
                    best_ev = ev_under
                    best_odds = under_odds
            elif ev_over is not None:
                best_side = 'over'
                best_ev = ev_over
                best_odds = over_odds
            elif ev_under is not None:
                best_side = 'under'
                best_ev = ev_under
                best_odds = under_odds
            else:
                continue
            
            ev_results[bookmaker] = {
                'over': ev_over,
                'under': ev_under,
                'best': best_side,
                'best_ev': best_ev,
                'best_odds': best_odds
            }
        
        return ev_results
    
    except Exception as e:
        print(f"Erro ao calcular EV de player prop: {e}")
        return {}