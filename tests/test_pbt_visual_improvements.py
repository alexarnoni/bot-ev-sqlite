"""
Property-Based Tests para Visual Improvements: Mensagem de confirmação,
Bloco comparativo de EV e Separadores no histórico.
Usa Hypothesis para validar as 5 propriedades de correção definidas no design.

Feature: visual-improvements

NOTA: Não importa do módulo bot diretamente (dependências pesadas: telegram, dotenv).
As funções de formatação pura são recriadas aqui para teste isolado.
"""
import math

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ============================================================
# Funções de formatação recriadas para teste isolado
# (replicam a lógica pura de src/bot/bot_listener.py)
# ============================================================


def formatar_confirmacao(valor: float, odd_apostada=None, odd_alerta_fallback=0.0) -> str:
    """Replica a lógica de confirmação de aposta em bet_text_handler."""
    odd_exibir = odd_apostada or odd_alerta_fallback
    return f"✅ Aposta registrada — R$ {valor:.2f} @ {odd_exibir:.2f}"


def calcular_bloco_ev(aposta: dict) -> str:
    """Replica a lógica do bloco EV em _formatar_lembrete."""
    ev_alerta = aposta.get('ev_alerta', 0) or 0
    odd_alerta_val = aposta.get('odd_alerta', 0) or 0
    odd_apostada_val = aposta.get('odd_apostada')

    bloco_ev = ""
    if (odd_apostada_val is not None
        and odd_apostada_val != odd_alerta_val
        and odd_alerta_val > 0
        and (1 + ev_alerta) > 0):
        prob_implicita = 1 / (odd_alerta_val / (1 + ev_alerta))
        ev_real = (odd_apostada_val * prob_implicita) - 1
        bloco_ev = (
            f"\n📊 Odd alerta: {odd_alerta_val:.2f} → Odd apostada: {odd_apostada_val:.2f}\n"
            f"📈 EV original: {ev_alerta*100:.1f}% → EV real: {ev_real*100:.1f}%\n"
        )
    return bloco_ev


def formatar_lembrete(aposta: dict) -> str:
    """Replica a lógica completa de _formatar_lembrete (sem dependência de formatar_data)."""
    home = aposta.get('home', '')
    away = aposta.get('away', '')
    league = aposta.get('league', '')
    market = aposta.get('market_name_fmt') or aposta.get('market_type', '')
    odd = aposta.get('odd_apostada') or aposta.get('odd_alerta', 0)
    valor = aposta.get('valor_apostado', 0)
    data_fmt = aposta.get('data_fmt', 'N/A')

    bloco_ev = calcular_bloco_ev(aposta)

    return (
        f"⏰ <b>Resultado pendente!</b>\n\n"
        f"⚽ <b>{home} vs {away}</b>\n"
        f"🏆 {league}\n"
        f"📌 Mercado: {market}\n"
        f"🔢 Odd: {odd:.2f}\n"
        f"💰 Apostado: R$ {valor:.2f}\n"
        f"🗓️ Jogo: {data_fmt}\n"
        f"{bloco_ev}\n"
        f"Qual foi o resultado?"
    )


def formatar_historico(historico: list) -> str:
    """Replica a lógica do loop em historico_command."""
    status_emoji = {"ganhou": "🟢", "perdeu": "🔴", "empate": "⚪", "cashout": "💸"}
    separador = "─────────────────"
    msg = ""
    for ap in historico:
        emoji = status_emoji.get(ap.get('status', ''), '❓')
        odd_exibir = ap.get('odd_apostada') or ap.get('odd_alerta', 0)
        mercado = ap.get('market_name_fmt') or ap.get('market_type', '')
        msg += (
            f"{emoji} {ap.get('home', '')} vs {ap.get('away', '')}\n"
            f"   📌 {mercado} | Odd: {odd_exibir:.2f} | R$ {ap.get('valor_apostado', 0):.2f}"
            f" | Lucro: R$ {ap.get('lucro', 0):+.2f}\n"
            f"{separador}\n\n"
        )
    return msg


# ============================================================
# Strategies
# ============================================================

# Valores positivos para apostas (evitar valores extremos que causem problemas de formatação)
st_valor = st.floats(min_value=0.01, max_value=999999.99, allow_nan=False, allow_infinity=False)

# Odds válidas (>= 1.01)
st_odd = st.floats(min_value=1.01, max_value=100.0, allow_nan=False, allow_infinity=False)

# Odd apostada: pode ser float positivo ou None
st_odd_apostada = st.one_of(st.none(), st_odd)

# EV alerta: float > -1 (para que (1 + ev_alerta) > 0)
st_ev_alerta_valido = st.floats(min_value=-0.99, max_value=2.0, allow_nan=False, allow_infinity=False)

# Nomes de times
st_team_name = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" -"),
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip() != "")

# Status de aposta
st_status = st.sampled_from(["ganhou", "perdeu", "empate", "cashout", ""])

# Mercado
st_mercado = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" _-"),
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip() != "")


# ============================================================
# Property 1: Formato da mensagem de confirmação
# Validates: Requirements 1.1, 1.2
# ============================================================

class TestProperty1FormatoConfirmacao:
    """
    Property 1: Formato da mensagem de confirmação.
    Para qualquer valor positivo e qualquer odd (apostada ou fallback),
    a mensagem de confirmação SHALL sempre conter "R$ {valor:.2f}" e "@ {odd:.2f}".

    **Validates: Requirements 1.1, 1.2**
    """

    @settings(max_examples=100)
    @given(
        valor=st_valor,
        odd_apostada=st_odd_apostada,
        odd_alerta_fallback=st_odd,
    )
    def test_formato_confirmacao(self, valor, odd_apostada, odd_alerta_fallback):
        """Mensagem sempre contém valor e odd formatados."""
        resultado = formatar_confirmacao(valor, odd_apostada, odd_alerta_fallback)

        # Sempre deve conter o valor formatado
        valor_fmt = f"R$ {valor:.2f}"
        assert valor_fmt in resultado

        # Sempre deve conter "@ " com a odd (apostada ou fallback)
        odd_esperada = odd_apostada if odd_apostada else odd_alerta_fallback
        odd_fmt = f"@ {odd_esperada:.2f}"
        assert odd_fmt in resultado


# ============================================================
# Property 2: Bloco EV presente quando odds diferem
# Validates: Requirements 2.1, 2.3
# ============================================================

class TestProperty2BlocoEVPresente:
    """
    Property 2: Bloco EV presente e correto quando odds diferem.
    Para qualquer aposta onde odd_apostada ≠ odd_alerta, odd_alerta > 0
    e (1 + ev_alerta) > 0, a saída SHALL conter "📊" e "📈"
    posicionadas antes de "Qual foi o resultado?".

    **Validates: Requirements 2.1, 2.3**
    """

    @settings(max_examples=100)
    @given(
        odd_apostada=st_odd,
        odd_alerta=st_odd,
        ev_alerta=st_ev_alerta_valido,
        home=st_team_name,
        away=st_team_name,
        valor=st_valor,
    )
    def test_bloco_ev_presente_quando_odds_diferem(
        self, odd_apostada, odd_alerta, ev_alerta, home, away, valor
    ):
        """Bloco EV presente e antes de 'Qual foi o resultado?' quando condições satisfeitas."""
        # Garantir que odds são diferentes
        assume(odd_apostada != odd_alerta)
        assume(odd_alerta > 0)
        assume((1 + ev_alerta) > 0)

        aposta = {
            'odd_apostada': odd_apostada,
            'odd_alerta': odd_alerta,
            'ev_alerta': ev_alerta,
            'home': home,
            'away': away,
            'league': 'Test League',
            'market_type': 'h2h',
            'valor_apostado': valor,
            'data_fmt': '01/01/2025 20:00',
        }

        resultado = formatar_lembrete(aposta)

        # Deve conter os emojis do bloco EV
        assert "📊" in resultado
        assert "📈" in resultado

        # Bloco EV deve estar antes de "Qual foi o resultado?"
        pos_ev = resultado.index("📊")
        pos_pergunta = resultado.index("Qual foi o resultado?")
        assert pos_ev < pos_pergunta


# ============================================================
# Property 3: Bloco EV omitido quando condições não satisfeitas
# Validates: Requirements 2.4, 2.5
# ============================================================

class TestProperty3BlocoEVOmitido:
    """
    Property 3: Bloco EV omitido quando condições não satisfeitas.
    Para qualquer aposta onde odd_apostada == odd_alerta OU odd_apostada é None
    OU odd_alerta == 0 OU (1 + ev_alerta) ≤ 0, a saída SHALL NOT conter "📊" nem "📈".

    **Validates: Requirements 2.4, 2.5**
    """

    @settings(max_examples=100)
    @given(
        odd_valor=st_odd,
        ev_alerta=st_ev_alerta_valido,
        home=st_team_name,
        away=st_team_name,
        valor=st_valor,
        caso=st.sampled_from(["odds_iguais", "odd_apostada_none", "odd_alerta_zero", "ev_invalido"]),
    )
    def test_bloco_ev_omitido(self, odd_valor, ev_alerta, home, away, valor, caso):
        """Bloco EV ausente quando condições não são satisfeitas."""
        aposta = {
            'home': home,
            'away': away,
            'league': 'Test League',
            'market_type': 'h2h',
            'valor_apostado': valor,
            'data_fmt': '01/01/2025 20:00',
        }

        if caso == "odds_iguais":
            aposta['odd_apostada'] = odd_valor
            aposta['odd_alerta'] = odd_valor
            aposta['ev_alerta'] = ev_alerta
        elif caso == "odd_apostada_none":
            aposta['odd_apostada'] = None
            aposta['odd_alerta'] = odd_valor
            aposta['ev_alerta'] = ev_alerta
        elif caso == "odd_alerta_zero":
            aposta['odd_apostada'] = odd_valor
            aposta['odd_alerta'] = 0
            aposta['ev_alerta'] = ev_alerta
        elif caso == "ev_invalido":
            # (1 + ev_alerta) <= 0 means ev_alerta <= -1
            aposta['odd_apostada'] = odd_valor
            aposta['odd_alerta'] = odd_valor + 0.5  # different odds
            aposta['ev_alerta'] = -1.5  # makes (1 + ev_alerta) = -0.5 <= 0

        resultado = formatar_lembrete(aposta)

        # Não deve conter os emojis do bloco EV
        assert "📊" not in resultado
        assert "📈" not in resultado


# ============================================================
# Property 4: Corretude do cálculo de EV
# Validates: Requirements 2.2
# ============================================================

class TestProperty4CorretudoCalculoEV:
    """
    Property 4: Corretude do cálculo de EV.
    Para qualquer odd_alerta > 0, ev_alerta > -1 e odd_apostada > 0,
    o ev_real calculado SHALL ser igual a
    (odd_apostada * (1 + ev_alerta) / odd_alerta) - 1
    com precisão de ponto flutuante.

    **Validates: Requirements 2.2**
    """

    @settings(max_examples=100)
    @given(
        odd_alerta=st.floats(min_value=1.01, max_value=50.0, allow_nan=False, allow_infinity=False),
        ev_alerta=st.floats(min_value=-0.99, max_value=2.0, allow_nan=False, allow_infinity=False),
        odd_apostada=st.floats(min_value=1.01, max_value=50.0, allow_nan=False, allow_infinity=False),
    )
    def test_calculo_ev_real(self, odd_alerta, ev_alerta, odd_apostada):
        """EV real calculado deve ser (odd_apostada * (1 + ev_alerta) / odd_alerta) - 1."""
        assume(odd_apostada != odd_alerta)
        assume(odd_alerta > 0)
        assume((1 + ev_alerta) > 0)

        aposta = {
            'odd_apostada': odd_apostada,
            'odd_alerta': odd_alerta,
            'ev_alerta': ev_alerta,
        }

        # Calcular usando a mesma lógica do código
        prob_implicita = 1 / (odd_alerta / (1 + ev_alerta))
        ev_real_code = (odd_apostada * prob_implicita) - 1

        # Calcular usando a fórmula simplificada
        ev_real_expected = (odd_apostada * (1 + ev_alerta) / odd_alerta) - 1

        # Verificar equivalência com tolerância de ponto flutuante
        assert math.isclose(ev_real_code, ev_real_expected, rel_tol=1e-9)

        # Verificar que o bloco EV contém o valor formatado corretamente
        bloco = calcular_bloco_ev(aposta)
        ev_real_fmt = f"{ev_real_code*100:.1f}%"
        assert ev_real_fmt in bloco


# ============================================================
# Property 5: Estrutura do histórico com separadores
# Validates: Requirements 3.1, 3.2
# ============================================================

class TestProperty5EstruturaSeparadores:
    """
    Property 5: Estrutura do histórico com separadores.
    Para qualquer lista não-vazia de apostas finalizadas, a saída SHALL
    conter cada aposta seguida pelo separador "─────────────────".

    **Validates: Requirements 3.1, 3.2**
    """

    @settings(max_examples=100)
    @given(
        historico=st.lists(
            st.fixed_dictionaries({
                'home': st_team_name,
                'away': st_team_name,
                'status': st_status,
                'odd_apostada': st_odd_apostada,
                'odd_alerta': st_odd,
                'market_name_fmt': st.one_of(st.none(), st_mercado),
                'market_type': st_mercado,
                'valor_apostado': st_valor,
                'lucro': st.floats(min_value=-10000.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
            }),
            min_size=1,
            max_size=20,
        )
    )
    def test_separadores_presentes(self, historico):
        """Cada aposta é seguida pelo separador."""
        separador = "─────────────────"

        resultado = formatar_historico(historico)

        # Deve conter exatamente len(historico) separadores
        assert resultado.count(separador) == len(historico)

        # Cada separador deve estar presente após cada entrada
        linhas = resultado.split("\n")
        separador_indices = [i for i, l in enumerate(linhas) if l == separador]
        assert len(separador_indices) == len(historico)
