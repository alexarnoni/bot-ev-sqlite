# ev_utils.py
from __future__ import annotations
from typing import Optional, Dict, Tuple, Iterable
import math
import statistics

# ---- Odds helpers -----------------------------------------------------------

def parse_odds(odd) -> Optional[float]:
    """
    Converte qualquer formato para decimal:
    - '1.90' -> 1.90
    - 1.9 -> 1.9
    - '+120' -> 2.20
    - '-150' -> 1.666...
    Retorna None se não der pra converter ou odd <= 1.0
    """
    if odd is None:
        return None
    try:
        # já decimal?
        if isinstance(odd, (int, float)):
            odd = float(odd)
            return odd if odd > 1.0 else None
        s = str(odd).strip() if hasattr(odd, 'strip') else str(odd)
        if not s:
            return None
        # americano
        if s.startswith(("+", "-")):
            v = int(s)
            if v > 0:
                return 1.0 + (v / 100.0)
            else:
                return 1.0 + (100.0 / abs(v))
        # decimal
        d = float(s.replace(",", "."))
        return d if d > 1.0 else None
    except Exception:
        return None

def implied_prob(odd_decimal: float) -> float:
    return 1.0 / odd_decimal

def no_vig_pair_probs(odd_over: float, odd_under: float) -> Tuple[float, float]:
    """
    Remove o vig com base em um par O/U.
    Retorna (p_over_fair, p_under_fair) que somam 1.
    """
    p_o = implied_prob(odd_over)
    p_u = implied_prob(odd_under)
    s = p_o + p_u
    if s <= 0:
        # fallback (quase impossível)
        return 0.5, 0.5
    return p_o / s, p_u / s

def fair_price_from_prob(p: float) -> float:
    """Preço justo (decimal) a partir de probabilidade fair."""
    if p <= 0:
        return math.inf
    return 1.0 / p

# ---- Consolidação por mercado ----------------------------------------------

def best_prices_over_under(bookmaker_odds: Dict) -> Tuple[Optional[Tuple[str,float]], Optional[Tuple[str,float]]]:
    """
    Recebe um dict semelhante a:
      {
        "Bet365": {"over": "1.95", "under": "1.83"},
        "Betano": {"over": "+105", "under": "-110"},
        ...
      }
    Retorna tuplas: (casa, odd_decimal) para melhor Over e melhor Under.
    """
    best_over = None   # (casa, odd)
    best_under = None
    for casa, lados in (bookmaker_odds or {}).items():
        if not isinstance(lados, dict):
            continue
        o = parse_odds(lados.get("over"))
        u = parse_odds(lados.get("under"))
        if o and (best_over is None or o > best_over[1]):
            best_over = (casa, o)
        if u and (best_under is None or u > best_under[1]):
            best_under = (casa, u)
    return best_over, best_under

def consensus_no_vig_prob(bookmaker_odds: Dict) -> Optional[float]:
    """
    Tenta formar uma probabilidade fair para Over a partir de TODOS os pares disponíveis,
    removendo o vig por par e depois tirando a mediana das probabilidades.
    Retorna p_over_fair (0..1) ou None se não houver material suficiente.
    """
    probs = []
    for _, lados in (bookmaker_odds or {}).items():
        if not isinstance(lados, dict):
            continue
        o = parse_odds(lados.get("over"))
        u = parse_odds(lados.get("under"))
        if o and u:
            p_over, _ = no_vig_pair_probs(o, u)
            probs.append(p_over)
    if not probs:
        return None
    # mediana é mais robusta a outliers
    return float(statistics.median(probs))

# ---- EV ---------------------------------------------------------------------

def calc_ev_for_side(odd_offer: float, p_fair: float) -> float:
    """
    EV do apostador dado preço de oferta (decimal) e prob. fair do evento.
    EV = p*odd - 1
    """
    return (p_fair * odd_offer) - 1.0

def calc_ev_prop(bookmaker_odds: Dict, side: str, offer_casa: Optional[str]=None, offer_odd_raw=None) -> Dict:
    """
    side: 'over' ou 'under' (ou qualquer string; será normalizada)
    - Se offer_casa/offer_odd_raw forem fornecidos (a oferta "que vamos enviar") usamos ela.
      Caso contrário, usamos o melhor preço do lado escolhido.
    - Probabilidade fair é a mediana no-vig construída a partir dos pares disponíveis.
      Se faltar um lado em todos os books, tenta cruzar melhor Over e melhor Under entre casas.
    Retorna dict com:
      {
        "ev": float or None,
        "p_fair": float or None,
        "offer_casa": str or None,
        "offer_odd": float or None,
        "best_over": (casa, odd) or None,
        "best_under": (casa, odd) or None,
      }
    """
    side = (side or "").strip().lower()
    if side not in ("over", "under"):
        # padrão: tratar como over
        side = "over"

    best_over, best_under = best_prices_over_under(bookmaker_odds)

    # Probabilidade fair pela mediana de pares
    p_over_fair = consensus_no_vig_prob(bookmaker_odds)

    # Se não deu pra obter p_over_fair, tentar cruzar melhor Over e melhor Under entre casas
    if p_over_fair is None and best_over and best_under:
        p_over_fair, _ = no_vig_pair_probs(best_over[1], best_under[1])

    if p_over_fair is None:
        # Sem material para estimar EV
        return {
            "ev": None, "p_fair": None,
            "offer_casa": offer_casa, "offer_odd": parse_odds(offer_odd_raw),
            "best_over": best_over, "best_under": best_under,
        }

    # Definir a oferta (casa/odd) do lado escolhido
    if offer_casa and offer_odd_raw:
        offer_odd = parse_odds(offer_odd_raw)
        offer = (offer_casa, offer_odd) if offer_odd else None
    else:
        offer = best_over if side == "over" else best_under

    if not offer or not offer[1]:
        # não temos preço para o lado escolhido
        return {
            "ev": None, "p_fair": p_over_fair if side=="over" else (1.0 - p_over_fair),
            "offer_casa": offer_casa, "offer_odd": None,
            "best_over": best_over, "best_under": best_under,
        }

    p_side = p_over_fair if side == "over" else (1.0 - p_over_fair)
    ev = calc_ev_for_side(offer[1], p_side)

    return {
        "ev": ev,
        "p_fair": p_side,
        "offer_casa": offer[0],
        "offer_odd": offer[1],
        "best_over": best_over,
        "best_under": best_under,
    }
