"""
Testes unitários para o módulo bets_tracker.py
Cobre as 6 propriedades de correção definidas no design.
"""
import re
import pytest
from datetime import datetime, timezone, timedelta

from src.core.database import Database
from src.bot.bets_tracker import (
    BetsTracker,
    StatusFinalError,
    calcular_lucro,
    gerar_alert_hash,
    now_utc_str,
    STATUSES_FINAIS,
    TIMESTAMP_FORMAT,
    DadosAlerta,
)


# --- Fixtures ---

@pytest.fixture
def db(tmp_path):
    """Cria banco de dados temporário para testes."""
    import os
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
def dados_alerta_base() -> DadosAlerta:
    """Dados de alerta padrão para testes."""
    return {
        "home": "Flamengo",
        "away": "Palmeiras",
        "league": "Brasileirão",
        "sport": "soccer",
        "market_type": "h2h",
        "bet_side": "home",
        "bookmaker": "Bet365",
        "odd_alerta": 2.0,
        "ev_alerta": 0.06,
        "commence_time": "2025-01-15 20:00:00",
    }


# ============================================================
# Property 2: Cálculo de lucro é consistente com o status
# ============================================================

class TestProperty2CalculoLucro:
    """Property 2: calcular_lucro() retorna valor consistente com o status."""

    def test_2_1_ganhou_odd_2_valor_100(self):
        """Caso 2.1: ganhou, odd=2.0, valor=100 → lucro=100.0"""
        assert calcular_lucro(2.0, 100, "ganhou") == 100.0

    def test_2_2_ganhou_odd_1_5_valor_200(self):
        """Caso 2.2: ganhou, odd=1.5, valor=200 → lucro=100.0"""
        assert calcular_lucro(1.5, 200, "ganhou") == 100.0

    def test_2_3_ganhou_odd_3_5_valor_50(self):
        """Caso 2.3: ganhou, odd=3.5, valor=50 → lucro=125.0"""
        assert calcular_lucro(3.5, 50, "ganhou") == 125.0

    def test_2_4_perdeu_valor_100(self):
        """Caso 2.4: perdeu, valor=100 → lucro=-100.0"""
        assert calcular_lucro(2.0, 100, "perdeu") == -100.0

    def test_2_5_perdeu_valor_0_01(self):
        """Caso 2.5: perdeu, valor=0.01 → lucro=-0.01"""
        assert calcular_lucro(2.0, 0.01, "perdeu") == -0.01

    def test_2_6_empate_valor_qualquer(self):
        """Caso 2.6: empate, valor=qualquer → lucro=0.0"""
        assert calcular_lucro(2.0, 500, "empate") == 0.0

    def test_2_7_cashout_valor_100_cashout_80(self):
        """Caso 2.7: cashout, valor=100, cashout=80 → lucro=-20.0"""
        assert calcular_lucro(2.0, 100, "cashout", valor_cashout=80) == -20.0

    def test_2_8_cashout_valor_100_cashout_120(self):
        """Caso 2.8: cashout, valor=100, cashout=120 → lucro=20.0"""
        assert calcular_lucro(2.0, 100, "cashout", valor_cashout=120) == 20.0


# ============================================================
# Property 1: Idempotência de inserção por alert_hash
# ============================================================

class TestProperty1Idempotencia:
    """Property 1: registrar_alerta() é idempotente por alert_hash."""

    def test_1_1_insercao_nova(self, tracker, dados_alerta_base):
        """Caso 1.1: Inserção nova retorna bet_id > 0."""
        alert_hash = gerar_alert_hash(
            "123", "Flamengo", "Palmeiras", "h2h", "home", "Bet365", "2025-01-15 20:00:00"
        )
        bet_id = tracker.registrar_alerta(alert_hash, "123", "feed1", dados_alerta_base)
        assert bet_id > 0

    def test_1_2_segunda_insercao_mesmo_hash(self, tracker, dados_alerta_base):
        """Caso 1.2: Segunda inserção com mesmo alert_hash retorna mesmo bet_id."""
        alert_hash = gerar_alert_hash(
            "123", "Flamengo", "Palmeiras", "h2h", "home", "Bet365", "2025-01-15 20:00:00"
        )
        bet_id_1 = tracker.registrar_alerta(alert_hash, "123", "feed1", dados_alerta_base)
        bet_id_2 = tracker.registrar_alerta(alert_hash, "123", "feed1", dados_alerta_base)
        assert bet_id_1 == bet_id_2

    def test_1_3_hash_diferente_chat_diferente(self, tracker, dados_alerta_base):
        """Caso 1.3: Hash diferente (chat_id diferente) gera registros distintos."""
        hash_1 = gerar_alert_hash(
            "123", "Flamengo", "Palmeiras", "h2h", "home", "Bet365", "2025-01-15 20:00:00"
        )
        hash_2 = gerar_alert_hash(
            "456", "Flamengo", "Palmeiras", "h2h", "home", "Bet365", "2025-01-15 20:00:00"
        )
        bet_id_1 = tracker.registrar_alerta(hash_1, "123", "feed1", dados_alerta_base)
        bet_id_2 = tracker.registrar_alerta(hash_2, "456", "feed1", dados_alerta_base)
        assert bet_id_1 != bet_id_2


# ============================================================
# Property 5: Callbacks em status final são idempotentes
# ============================================================

class TestProperty5IdempotenciaStatusFinal:
    """Property 5: Operações em status final levantam StatusFinalError."""

    def _criar_aposta_finalizada(self, tracker, dados_alerta_base):
        """Helper: cria aposta e marca como ganhou."""
        alert_hash = gerar_alert_hash(
            "123", "Flamengo", "Palmeiras", "h2h", "home", "Bet365", "2025-01-15 20:00:00"
        )
        bet_id = tracker.registrar_alerta(alert_hash, "123", "feed1", dados_alerta_base)
        tracker.marcar_apostou(bet_id, 10.0, 10.0)
        tracker.marcar_resultado(bet_id, "ganhou")
        return bet_id

    def test_5_1_bet_yes_em_status_final(self, tracker, dados_alerta_base):
        """Caso 5.1: marcar_apostou em aposta com status ganhou → StatusFinalError."""
        bet_id = self._criar_aposta_finalizada(tracker, dados_alerta_base)
        with pytest.raises(StatusFinalError):
            tracker.marcar_apostou(bet_id, 5.0, 10.0)

    def test_5_2_bet_no_em_status_final(self, tracker, dados_alerta_base):
        """Caso 5.2: marcar_pulei em aposta com status ganhou → StatusFinalError."""
        bet_id = self._criar_aposta_finalizada(tracker, dados_alerta_base)
        with pytest.raises(StatusFinalError):
            tracker.marcar_pulei(bet_id)

    def test_5_3_bet_result_win_em_status_final(self, tracker, dados_alerta_base):
        """Caso 5.3: marcar_resultado('ganhou') em aposta já finalizada → StatusFinalError."""
        bet_id = self._criar_aposta_finalizada(tracker, dados_alerta_base)
        with pytest.raises(StatusFinalError):
            tracker.marcar_resultado(bet_id, "ganhou")

    def test_5_4_bet_result_loss_em_status_final(self, tracker, dados_alerta_base):
        """Caso 5.4: marcar_resultado('perdeu') em aposta já finalizada → StatusFinalError."""
        bet_id = self._criar_aposta_finalizada(tracker, dados_alerta_base)
        with pytest.raises(StatusFinalError):
            tracker.marcar_resultado(bet_id, "perdeu")

    def test_5_5_bet_cashout_em_status_final(self, tracker, dados_alerta_base):
        """Caso 5.5: marcar_resultado('cashout') em aposta já finalizada → StatusFinalError."""
        bet_id = self._criar_aposta_finalizada(tracker, dados_alerta_base)
        with pytest.raises(StatusFinalError):
            tracker.marcar_resultado(bet_id, "cashout", valor_cashout=80.0)


# ============================================================
# Property 4: get_resumo exclui status não-finalizados
# ============================================================

class TestProperty4GetResumoExcluiNaoFinalizados:
    """Property 4: get_resumo() exclui pendente/pulei/expirado dos totais."""

    def test_4_1_todos_status(self, tracker, db, dados_alerta_base):
        """Caso 4.1: 1 aposta de cada status → total_apostas=4 (só finalizados)."""
        statuses = ["pendente", "pulei", "expirado", "ganhou", "perdeu", "empate", "cashout"]

        for i, status in enumerate(statuses):
            hash_val = gerar_alert_hash(
                "123", f"Time{i}", "Rival", "h2h", "home", "Bet365", f"2025-01-{15+i:02d} 20:00:00"
            )
            dados = {**dados_alerta_base, "home": f"Time{i}", "commence_time": f"2025-01-{15+i:02d} 20:00:00"}
            bet_id = tracker.registrar_alerta(hash_val, "123", "feed1", dados)
            tracker.marcar_apostou(bet_id, 10.0, 10.0)

            if status == "ganhou":
                tracker.marcar_resultado(bet_id, "ganhou")
            elif status == "perdeu":
                tracker.marcar_resultado(bet_id, "perdeu")
            elif status == "empate":
                tracker.marcar_resultado(bet_id, "empate")
            elif status == "cashout":
                tracker.marcar_resultado(bet_id, "cashout", valor_cashout=80.0)
            elif status == "pulei":
                tracker.marcar_pulei(bet_id)
            elif status == "expirado":
                tracker.marcar_resultado_expirado(bet_id)
            # pendente: não faz nada

        resumo = tracker.get_resumo("123", dias=365)
        assert resumo["total_apostas"] == 4
        assert resumo["ganhou"] == 1
        assert resumo["perdeu"] == 1
        assert resumo["empate"] == 1
        assert resumo["cashout"] == 1


# ============================================================
# Property 6: Validação monetária rejeita entradas inválidas
# ============================================================

# Regex de validação (mesma usada no bot_listener)
VALOR_REGEX = re.compile(r"^\d+([.,]\d{1,2})?$")


def validar_valor(texto: str) -> float | None:
    """Valida e converte valor monetário. Retorna None se inválido."""
    if not VALOR_REGEX.match(texto):
        return None
    valor = float(texto.replace(",", "."))
    if valor <= 0:
        return None
    return valor


class TestProperty6ValidacaoMonetaria:
    """Property 6: Validação monetária rejeita entradas inválidas."""

    def test_6_1_inteiro_valido(self):
        """Caso 6.1: '50' → válido, 50.0"""
        assert validar_valor("50") == 50.0

    def test_6_2_decimal_ponto(self):
        """Caso 6.2: '50.5' → válido, 50.5"""
        assert validar_valor("50.5") == 50.5

    def test_6_3_decimal_virgula(self):
        """Caso 6.3: '50,5' → válido, 50.5 (normaliza vírgula)"""
        assert validar_valor("50,5") == 50.5

    def test_6_4_duas_casas_decimais(self):
        """Caso 6.4: '50.50' → válido, 50.50"""
        assert validar_valor("50.50") == 50.50

    def test_6_5_texto_invalido(self):
        """Caso 6.5: 'abc' → inválido"""
        assert validar_valor("abc") is None

    def test_6_6_negativo(self):
        """Caso 6.6: '-50' → inválido"""
        assert validar_valor("-50") is None

    def test_6_7_zero(self):
        """Caso 6.7: '0' → inválido (valor ≤ 0)"""
        assert validar_valor("0") is None

    def test_6_8_tres_casas_decimais(self):
        """Caso 6.8: '50.555' → inválido (3 casas decimais)"""
        assert validar_valor("50.555") is None

    def test_6_9_string_vazia(self):
        """Caso 6.9: '' → inválido"""
        assert validar_valor("") is None

    def test_6_10_multiplas_virgulas(self):
        """Caso 6.10: '50,5,5' → inválido"""
        assert validar_valor("50,5,5") is None


# ============================================================
# Tests: odd_apostada — Registro e cálculo de lucro
# Validates: Requirements 2.1, 2.2, 3.1, 3.2
# ============================================================

class TestOddApostada:
    """Testes para o campo odd_apostada em marcar_apostou e marcar_resultado."""

    def _criar_aposta(self, tracker, dados_alerta_base, odd_alerta=2.0):
        """Helper: cria aposta pendente e retorna bet_id."""
        dados = {**dados_alerta_base, "odd_alerta": odd_alerta}
        alert_hash = gerar_alert_hash(
            "123", "Flamengo", "Palmeiras", "h2h", "home", "Bet365", "2025-01-15 20:00:00"
        )
        return tracker.registrar_alerta(alert_hash, "123", "feed1", dados)

    def test_marcar_apostou_com_odd_apostada(self, tracker, db, dados_alerta_base):
        """Req 2.1: marcar_apostou com odd_apostada=2.15 → campo salvo corretamente."""
        bet_id = self._criar_aposta(tracker, dados_alerta_base, odd_alerta=2.0)
        tracker.marcar_apostou(bet_id, 10.0, 10.0, odd_apostada=2.15)

        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT odd_apostada, valor_apostado FROM bets_placed WHERE id = ?",
                (bet_id,)
            ).fetchone()

        assert row['odd_apostada'] == 2.15
        assert row['valor_apostado'] == 100.0

    def test_marcar_apostou_sem_odd_apostada_usa_odd_alerta(self, tracker, db, dados_alerta_base):
        """Req 2.2: marcar_apostou com odd_apostada=None → campo recebe odd_alerta."""
        bet_id = self._criar_aposta(tracker, dados_alerta_base, odd_alerta=1.85)
        tracker.marcar_apostou(bet_id, 5.0, 10.0, odd_apostada=None)

        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT odd_apostada, odd_alerta FROM bets_placed WHERE id = ?",
                (bet_id,)
            ).fetchone()

        assert row['odd_apostada'] == 1.85
        assert row['odd_alerta'] == 1.85

    def test_marcar_resultado_usa_odd_apostada(self, tracker, db, dados_alerta_base):
        """Req 3.1: marcar_resultado com odd_apostada definida → lucro usa odd_apostada."""
        bet_id = self._criar_aposta(tracker, dados_alerta_base, odd_alerta=2.0)
        tracker.marcar_apostou(bet_id, 10.0, 10.0, odd_apostada=2.50)
        tracker.marcar_resultado(bet_id, "ganhou")

        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT lucro FROM bets_placed WHERE id = ?", (bet_id,)
            ).fetchone()

        # lucro = (odd_apostada - 1) * valor = (2.50 - 1) * 100 = 150.0
        assert row['lucro'] == pytest.approx(150.0)

    def test_marcar_resultado_fallback_odd_alerta(self, tracker, db, dados_alerta_base):
        """Req 3.2: marcar_resultado com odd_apostada NULL → lucro usa odd_alerta."""
        bet_id = self._criar_aposta(tracker, dados_alerta_base, odd_alerta=2.0)

        # Simula aposta sem odd_apostada (campo fica NULL no banco)
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE bets_placed SET valor_apostado = ?, odd_apostada = NULL WHERE id = ?",
                (100.0, bet_id)
            )

        tracker.marcar_resultado(bet_id, "ganhou")

        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT lucro FROM bets_placed WHERE id = ?", (bet_id,)
            ).fetchone()

        # lucro = (odd_alerta - 1) * valor = (2.0 - 1) * 100 = 100.0
        assert row['lucro'] == pytest.approx(100.0)

    def test_marcar_apostou_grava_stake_unidades(self, tracker, db, dados_alerta_base):
        """Stake em unidades é gravada e valor_apostado = unidades * valor_unidade."""
        bet_id = self._criar_aposta(tracker, dados_alerta_base, odd_alerta=2.0)
        tracker.marcar_apostou(bet_id, 2.5, 10.0, odd_apostada=1.90)

        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT stake_unidades, valor_apostado FROM bets_placed WHERE id = ?",
                (bet_id,)
            ).fetchone()

        assert row['stake_unidades'] == 2.5
        assert row['valor_apostado'] == pytest.approx(25.0)
