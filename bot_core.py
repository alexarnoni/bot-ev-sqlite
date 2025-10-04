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

def definir_stake(ev, odd, ev_minimo=0.05):
    """
    Define stake fixa com base apenas na odd:
    - Odds entre 1.50 e 3.50 → 1.0u
    - Odds entre 3.51 e 8.00 → 0.5u
    - Odds acima de 8.00     → 0.25u
    - Odds fora desses intervalos → 0.1u

    EV mínimo para considerar: configurável pelo usuário (padrão = 5%)
    Stake mínima: 0.10u

    Retorna: stake (float)
    """
    if ev < ev_minimo:
        return 0  # Ignora apostas abaixo do EV configurado

    try:
        odd = float(odd)
    except (TypeError, ValueError):
        return 0

    if 1.50 <= odd <= 3.50:
        stake = 1.0
    elif 3.51 <= odd <= 8.00:
        stake = 0.5
    elif odd > 8.00:
        stake = 0.25
    else:
        stake = 0.1

    return round(stake, 2)
