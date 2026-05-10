"""
Testes de preservação: comportamento baseline que DEVE ser mantido após a correção.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

Estes testes capturam o comportamento atual do código NÃO corrigido e devem
continuar passando após a implementação da correção (sem regressões).

Comportamentos preservados:
- _montar_aviso_mesmo_jogo([]) → string vazia
- _montar_aviso_mesmo_jogo com alertas sem market_name_fmt → produz output não-vazio
- registrar_alerta funciona para todos os tipos de mercado
- buscar_alertas_mesmo_jogo retorna dicts com as chaves esperadas
"""
import os
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from src.core.database import Database
from src.bot.bets_tracker import BetsTracker, gerar_alert_hash, DadosAlerta
from src.bot.bot_ev import AlertSender


# --- Fixtures ---

@pytest.fixture
def db(tmp_path):
    """Cria banco de dados temporário para testes."""
    os.environ["FEED_ID"] = "test"
    os.environ["BOT_DATA_ROOT"] = str(tmp_path)
    database = Database.__new__(Database)
    database.feed_id = "test"
    database.db_path = str(tmp_path / "test" / "bot.db")
    os.makedirs(tmp_path / "test", exist_ok=True)
    database._init_db()
    return database


@pytest.fixture
def tracker(db):
    """Cria instância de BetsTracker com banco temporário."""
    return BetsTracker(db)


@pytest.fixture
def sender(tracker):
    """Cria AlertSender minimal sem inicializar Telegram Bot."""
    s = AlertSender.__new__(AlertSender)
    s._bets_tracker = tracker
    return s


# --- Estratégias Hypothesis ---

market_types_st = st.sampled_from([
    "h2h", "totals", "spreads", "moneyline", "handicap",
    "player props - jogador (points)", "team total home",
    "team total away", "corners totals", "bookings totals",
    "match winner", "dnb", "btts",
])

bet_sides_st = st.sampled_from(["home", "away", "over", "under", "draw"])


# ============================================================
# Preservation 1: Lista vazia → string vazia
# ============================================================

class TestPreservacaoListaVazia:
    """
    Preservation: _montar_aviso_mesmo_jogo([]) retorna string vazia.

    **Validates: Requirements 3.2**
    """

    def test_lista_vazia_retorna_string_vazia(self, sender):
        """Lista vazia de alertas anteriores deve retornar string vazia."""
        resultado = sender._montar_aviso_mesmo_jogo([])
        assert resultado == ""

    def test_lista_vazia_tipo_string(self, sender):
        """Resultado deve ser do tipo str."""
        resultado = sender._montar_aviso_mesmo_jogo([])
        assert isinstance(resultado, str)


# ============================================================
# Preservation 2: Lista não-vazia → string não-vazia com info de odd
# ============================================================

class TestPreservacaoListaNaoVazia:
    """
    Preservation: _montar_aviso_mesmo_jogo com alertas produz output não-vazio
    contendo informações da odd.

    **Validates: Requirements 3.3**
    """

    def test_alerta_simples_produz_output(self, sender):
        """Um alerta com market_name_fmt=None (registro antigo) produz output não-vazio."""
        alertas = [{
            "id": 1,
            "market_type": "h2h",
            "bet_side": "home",
            "odd_alerta": 2.0,
            "odd_apostada": None,
            "ev_alerta": 0.06,
            "status": "pendente",
            "valor_apostado": None,
            "timestamp_alerta": "2025-01-15 20:00:00",
        }]
        resultado = sender._montar_aviso_mesmo_jogo(alertas)
        assert resultado != ""
        assert "Odd" in resultado

    def test_alerta_com_valor_apostado_mostra_apostado(self, sender):
        """Alerta com valor_apostado mostra indicador de apostado."""
        alertas = [{
            "id": 1,
            "market_type": "h2h",
            "bet_side": "home",
            "odd_alerta": 1.85,
            "odd_apostada": 1.85,
            "ev_alerta": 0.05,
            "status": "pendente",
            "valor_apostado": 100.0,
            "timestamp_alerta": "2025-01-15 20:00:00",
        }]
        resultado = sender._montar_aviso_mesmo_jogo(alertas)
        assert "Apostado" in resultado

    @given(
        market_type=market_types_st,
        bet_side=bet_sides_st,
        odd_alerta=st.floats(min_value=1.01, max_value=50.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pbt_qualquer_mercado_produz_output_com_odd(self, sender, market_type, bet_side, odd_alerta):
        """
        Property-based: para qualquer tipo de mercado e odd, o aviso produz
        output não-vazio contendo informação de odd formatada.

        **Validates: Requirements 3.3**
        """
        alertas = [{
            "id": 1,
            "market_type": market_type,
            "bet_side": bet_side,
            "odd_alerta": odd_alerta,
            "odd_apostada": None,
            "ev_alerta": 0.05,
            "status": "pendente",
            "valor_apostado": None,
            "timestamp_alerta": "2025-01-15 20:00:00",
        }]
        resultado = sender._montar_aviso_mesmo_jogo(alertas)
        assert resultado != "", f"Aviso vazio para market_type={market_type}"
        assert "Odd" in resultado, f"Aviso sem 'Odd' para market_type={market_type}"
        # O aviso deve conter o cabeçalho padrão
        assert "Já foi enviado alerta deste jogo" in resultado


# ============================================================
# Preservation 3: registrar_alerta funciona para todos os mercados
# ============================================================

class TestPreservacaoRegistrarAlerta:
    """
    Preservation: registrar_alerta continua funcionando para todos os tipos de mercado.

    **Validates: Requirements 3.4**
    """

    @given(
        market_type=market_types_st,
        bet_side=bet_sides_st,
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pbt_registrar_alerta_todos_mercados(self, db, tracker, market_type, bet_side):
        """
        Property-based: registrar_alerta retorna bet_id > 0 para qualquer
        combinação de market_type e bet_side.

        **Validates: Requirements 3.4**
        """
        chat_id = "test_user"
        home = "TimeA"
        away = "TimeB"
        commence_time = "2025-06-01 18:00:00"

        alert_hash = gerar_alert_hash(
            chat_id, home, away, market_type, bet_side, "Bet365", commence_time
        )
        dados_alerta: DadosAlerta = {
            "home": home,
            "away": away,
            "league": "Liga Teste",
            "sport": "soccer",
            "market_type": market_type,
            "bet_side": bet_side,
            "bookmaker": "Bet365",
            "odd_alerta": 1.90,
            "ev_alerta": 0.05,
            "commence_time": commence_time,
        }
        bet_id = tracker.registrar_alerta(alert_hash, chat_id, "feed1", dados_alerta)
        assert bet_id > 0, f"registrar_alerta falhou para market_type={market_type}, bet_side={bet_side}"


# ============================================================
# Preservation 4: buscar_alertas_mesmo_jogo retorna campos esperados
# ============================================================

class TestPreservacaoBuscarAlertas:
    """
    Preservation: buscar_alertas_mesmo_jogo retorna dicts com as chaves esperadas.

    **Validates: Requirements 3.1, 3.3**
    """

    def test_buscar_alertas_retorna_campos_esperados(self, tracker):
        """Após registrar alerta, buscar_alertas_mesmo_jogo retorna dict com chaves corretas."""
        chat_id = "12345"
        home = "Flamengo"
        away = "Palmeiras"
        commence_time = "2025-01-15 20:00:00"

        alert_hash = gerar_alert_hash(
            chat_id, home, away, "h2h", "home", "Bet365", commence_time
        )
        dados_alerta: DadosAlerta = {
            "home": home,
            "away": away,
            "league": "Brasileirão",
            "sport": "soccer",
            "market_type": "h2h",
            "bet_side": "home",
            "bookmaker": "Bet365",
            "odd_alerta": 2.0,
            "ev_alerta": 0.06,
            "commence_time": commence_time,
        }
        tracker.registrar_alerta(alert_hash, chat_id, "feed1", dados_alerta)

        alertas = tracker.buscar_alertas_mesmo_jogo(chat_id, home, away, commence_time)
        assert len(alertas) == 1

        alerta = alertas[0]
        # Chaves que DEVEM existir no resultado
        chaves_esperadas = {
            "id", "market_type", "bet_side", "odd_alerta",
            "odd_apostada", "ev_alerta", "status", "valor_apostado",
            "timestamp_alerta",
        }
        for chave in chaves_esperadas:
            assert chave in alerta, f"Chave '{chave}' ausente no resultado de buscar_alertas_mesmo_jogo"

        # Valores devem corresponder ao que foi registrado
        assert alerta["market_type"] == "h2h"
        assert alerta["bet_side"] == "home"
        assert alerta["odd_alerta"] == 2.0
        assert alerta["ev_alerta"] == 0.06

    @given(
        market_type=market_types_st,
        bet_side=bet_sides_st,
        odd_alerta=st.floats(min_value=1.01, max_value=50.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pbt_roundtrip_registrar_buscar(self, db, tracker, market_type, bet_side, odd_alerta):
        """
        Property-based: registrar_alerta + buscar_alertas_mesmo_jogo round-trip
        preserva market_type e bet_side.

        **Validates: Requirements 3.1, 3.3**
        """
        chat_id = "roundtrip_user"
        home = "TimeX"
        away = "TimeY"
        commence_time = "2025-03-10 15:00:00"

        alert_hash = gerar_alert_hash(
            chat_id, home, away, market_type, bet_side, "Pinnacle", commence_time
        )
        dados_alerta: DadosAlerta = {
            "home": home,
            "away": away,
            "league": "Liga PBT",
            "sport": "soccer",
            "market_type": market_type,
            "bet_side": bet_side,
            "bookmaker": "Pinnacle",
            "odd_alerta": odd_alerta,
            "ev_alerta": 0.04,
            "commence_time": commence_time,
        }
        tracker.registrar_alerta(alert_hash, chat_id, "feed1", dados_alerta)

        alertas = tracker.buscar_alertas_mesmo_jogo(chat_id, home, away, commence_time)
        assert len(alertas) >= 1

        # Encontra o alerta que acabamos de registrar
        encontrado = any(
            a["market_type"] == market_type and a["bet_side"] == bet_side
            for a in alertas
        )
        assert encontrado, (
            f"Alerta com market_type={market_type}, bet_side={bet_side} "
            f"não encontrado no resultado de buscar_alertas_mesmo_jogo"
        )
