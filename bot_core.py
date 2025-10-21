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
    SEGUINDO A LÓGICA DA DOCUMENTAÇÃO DA API
    
    Para cada casa, compara sua odd com a SEGUNDA MELHOR odd do mercado.
    Se a odd for significativamente maior, há EV+.
    
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
        
        if not bookmaker_odds or len(bookmaker_odds) < 2:
            return {}  # Precisa de pelo menos 2 casas para comparar
        
        # Coletar todas as odds por bookmaker
        all_overs = []  # [(bookmaker, odd), ...]
        all_unders = []
        
        for bookmaker, odds in bookmaker_odds.items():
            over = odds.get('over')
            under = odds.get('under')
            
            if over and over > 1.0:
                all_overs.append((bookmaker, over))
            if under and under > 1.0:
                all_unders.append((bookmaker, under))
        
        if not all_overs or not all_unders:
            return {}
        
        # Ordenar por odd (maior primeiro)
        all_overs.sort(key=lambda x: x[1], reverse=True)
        all_unders.sort(key=lambda x: x[1], reverse=True)
        
        # ESTRATÉGIA: Comparar com a SEGUNDA MELHOR odd (ou média se houver muitas casas)
        # Isso simula o "fair value" do mercado sem a melhor odd
        
        def get_fair_odd(sorted_odds):
            """Pega a segunda melhor odd, ou média das demais se houver 3+ casas"""
            if len(sorted_odds) < 2:
                return None
            
            # Se tiver 2 casas: usar a segunda (pior)
            if len(sorted_odds) == 2:
                return sorted_odds[1][1]  # Segunda odd
            
            # Se tiver 3+ casas: usar média das odds excluindo a melhor
            odds_sem_melhor = [odd for _, odd in sorted_odds[1:]]
            return sum(odds_sem_melhor) / len(odds_sem_melhor)
        
        fair_over = get_fair_odd(all_overs)
        fair_under = get_fair_odd(all_unders)
        
        if not fair_over or not fair_under:
            return {}
        
        # Calcular EV para cada casa comparando com o "fair value"
        ev_results = {}
        
        for bookmaker, odds in bookmaker_odds.items():
            over_odds = odds.get('over')
            under_odds = odds.get('under')
            
            ev_over = None
            ev_under = None
            
            # Calcular EV para over
            if over_odds and over_odds > 1.0:
                # EV = (odd / fair_odd) - 1
                # Se odd > fair_odd, há valor positivo
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
        import traceback
        traceback.print_exc()
        return {}