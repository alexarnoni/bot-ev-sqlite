"""
Testes unitários para BetsTracker.get_total_pendente.

Cobre:
- Soma correta de múltiplas apostas pendentes
- Apostas com valor_apostado IS NULL são ignoradas
- Apostas com outros status não entram na soma
- Chat sem pendentes retorna 0.0
- Isolamento por chat_id

Usa SQLite em memória via Database temporário, sem mocks.
"""
import os
import pytest

from src.core.database import Database
from src.bot.bets_tracker import BetsTracker, DadosAlerta, gerar_alert_hash


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    """Banco de dados temporário em arquivo (compatível com Database)."""
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
    return BetsTracker(db)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DADOS_BASE: DadosAlerta = {
    "home": "Time A",
    "away": "Time B",
    "league": "Liga X",
    "sport": "soccer",
    "market_type": "h2h",
    "bet_side": "home",
    "bookmaker": "Bet365",
    "odd_alerta": 2.0,
    "ev_alerta": 0.07,
    "commence_time": "2025-06-01 20:00:00",
}


def _registrar_e_apostar(
    tracker: BetsTracker,
    chat_id: str,
    stake_unidades: float,
    valor_unidade: float,
    suffix: str = "",
) -> int:
    """Registra alerta e marca como apostado. Retorna bet_id."""
    dados = dict(_DADOS_BASE)
    dados["home"] = f"Time A {suffix}"
    alert_hash = gerar_alert_hash(
        chat_id,
        dados["home"],
        dados["away"],
        dados["market_type"],
        dados["bet_side"],
        dados["bookmaker"],
        dados["commence_time"],
    )
    bet_id = tracker.registrar_alerta(alert_hash, chat_id, "feed_test", dados)
    tracker.marcar_apostou(bet_id, stake_unidades, valor_unidade)
    return bet_id


def _registrar_sem_apostar(
    tracker: BetsTracker,
    chat_id: str,
    suffix: str = "",
) -> int:
    """Registra alerta mas NÃO chama marcar_apostou (valor_apostado fica NULL)."""
    dados = dict(_DADOS_BASE)
    dados["home"] = f"Time A {suffix}"
    alert_hash = gerar_alert_hash(
        chat_id,
        dados["home"],
        dados["away"],
        dados["market_type"],
        dados["bet_side"],
        dados["bookmaker"],
        dados["commence_time"],
    )
    return tracker.registrar_alerta(alert_hash, chat_id, "feed_test", dados)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestGetTotalPendente:

    def test_sem_apostas_retorna_zero(self, tracker):
        """Chat sem nenhuma aposta deve retornar 0.0."""
        result = tracker.get_total_pendente("chat_vazio")
        assert result == 0.0

    def test_soma_multiplas_pendentes(self, tracker):
        """Soma correta de N apostas pendentes com valores diferentes."""
        chat_id = "chat_multi"
        tracker.configurar_bankroll(chat_id, 1000.0, 10.0)

        # 3 apostas: 1u×10, 2u×10, 3u×10 → 10 + 20 + 30 = 60
        _registrar_e_apostar(tracker, chat_id, 1.0, 10.0, suffix="1")
        _registrar_e_apostar(tracker, chat_id, 2.0, 10.0, suffix="2")
        _registrar_e_apostar(tracker, chat_id, 3.0, 10.0, suffix="3")

        assert tracker.get_total_pendente(chat_id) == pytest.approx(60.0)

    def test_valor_apostado_null_ignorado(self, tracker):
        """Apostas registradas mas sem confirmação (valor_apostado NULL) não entram na soma."""
        chat_id = "chat_null"

        # Aposta com valor
        _registrar_e_apostar(tracker, chat_id, 2.0, 10.0, suffix="com_valor")
        # Alerta sem confirmação (valor_apostado = NULL)
        _registrar_sem_apostar(tracker, chat_id, suffix="sem_valor")

        # Só a primeira deve contar: 2 × 10 = 20
        assert tracker.get_total_pendente(chat_id) == pytest.approx(20.0)

    def test_status_ganhou_nao_entra(self, tracker):
        """Aposta com status='ganhou' não deve aparecer no total pendente."""
        chat_id = "chat_ganhou"
        bet_id = _registrar_e_apostar(tracker, chat_id, 5.0, 10.0, suffix="g")
        tracker.marcar_resultado(bet_id, "ganhou")
        assert tracker.get_total_pendente(chat_id) == 0.0

    def test_status_perdeu_nao_entra(self, tracker):
        """Aposta com status='perdeu' não deve aparecer no total pendente."""
        chat_id = "chat_perdeu"
        bet_id = _registrar_e_apostar(tracker, chat_id, 5.0, 10.0, suffix="p")
        tracker.marcar_resultado(bet_id, "perdeu")
        assert tracker.get_total_pendente(chat_id) == 0.0

    def test_status_expirado_nao_entra(self, tracker):
        """Aposta com status='expirado' não deve aparecer no total pendente."""
        chat_id = "chat_expirado"
        bet_id = _registrar_e_apostar(tracker, chat_id, 5.0, 10.0, suffix="e")
        tracker.marcar_resultado_expirado(bet_id)
        assert tracker.get_total_pendente(chat_id) == 0.0

    def test_isolamento_por_chat_id(self, tracker):
        """Pendentes de outro chat_id não devem contaminar o resultado."""
        chat_a = "chat_isolado_A"
        chat_b = "chat_isolado_B"

        # Chat A tem 50 reais pendentes
        _registrar_e_apostar(tracker, chat_a, 5.0, 10.0, suffix="isolA")

        # Chat B tem 200 reais pendentes
        _registrar_e_apostar(tracker, chat_b, 20.0, 10.0, suffix="isolB")

        assert tracker.get_total_pendente(chat_a) == pytest.approx(50.0)
        assert tracker.get_total_pendente(chat_b) == pytest.approx(200.0)

    def test_misto_pendente_e_finalizado(self, tracker):
        """Com pendentes e finalizados, soma apenas os pendentes."""
        chat_id = "chat_misto"

        # Pendente: 3u × 10 = 30
        _registrar_e_apostar(tracker, chat_id, 3.0, 10.0, suffix="pend")

        # Finalizado (perdeu): 5u × 10 = 50 → não conta
        bet_id = _registrar_e_apostar(tracker, chat_id, 5.0, 10.0, suffix="fin")
        tracker.marcar_resultado(bet_id, "perdeu")

        assert tracker.get_total_pendente(chat_id) == pytest.approx(30.0)

    def test_retorno_e_float(self, tracker):
        """O tipo de retorno deve ser float."""
        result = tracker.get_total_pendente("chat_tipo")
        assert isinstance(result, float)
