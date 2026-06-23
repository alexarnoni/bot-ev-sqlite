"""
Testes para get_resumo_por_faixa_ev — ROI por faixa de EV.
Usa banco SQLite em memória, sem mocks.
"""
import os
import pytest

from src.core.database import Database
from src.bot.bets_tracker import BetsTracker


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
    return BetsTracker(db)


def _inserir_aposta(db, chat_id, ev_alerta, valor_apostado, lucro, status):
    """Helper para inserir aposta diretamente na tabela."""
    import hashlib
    from datetime import datetime, timezone
    alert_hash = hashlib.sha256(os.urandom(16)).hexdigest()[:32]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO bets_placed
            (alert_hash, chat_id, feed_id, home, away, market_type, bet_side,
             bookmaker, odd_alerta, ev_alerta, commence_time, valor_apostado,
             lucro, status, timestamp_alerta, timestamp_apostou, timestamp_resultado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert_hash, chat_id, "test", "TeamA", "TeamB", "h2h", "home",
            "Bet365", 2.0, ev_alerta, "2025-01-15 20:00:00", valor_apostado,
            lucro, status, ts, ts, ts,
        ))


class TestResumoPorFaixaEV:
    """Testes para get_resumo_por_faixa_ev."""

    def test_apostas_distribuidas_nas_tres_faixas(self, tracker, db):
        """Apostas distribuídas nas três faixas retornam ROI correto por faixa."""
        chat_id = "123"
        # Faixa 5-8%: 2 apostas, lucro total 5, investido 100 → ROI 5%
        _inserir_aposta(db, chat_id, ev_alerta=0.06, valor_apostado=50, lucro=3, status="ganhou")
        _inserir_aposta(db, chat_id, ev_alerta=0.07, valor_apostado=50, lucro=2, status="perdeu")
        # Faixa 8-12%: 1 aposta, lucro -10, investido 40 → ROI -25%
        _inserir_aposta(db, chat_id, ev_alerta=0.09, valor_apostado=40, lucro=-10, status="perdeu")
        # Faixa >12%: 1 aposta, lucro 20, investido 30 → ROI 66.67%
        _inserir_aposta(db, chat_id, ev_alerta=0.15, valor_apostado=30, lucro=20, status="ganhou")

        resultado = tracker.get_resumo_por_faixa_ev(chat_id)

        assert len(resultado) == 3
        # Verificar ordem: 5-8% primeiro
        assert resultado[0]['faixa'] == '5-8%'
        assert resultado[1]['faixa'] == '8-12%'
        assert resultado[2]['faixa'] == '>12%'

        # Faixa 5-8%
        assert resultado[0]['apostas'] == 2
        assert resultado[0]['lucro'] == 5.0
        assert resultado[0]['total_apostado'] == 100.0
        assert abs(resultado[0]['roi_pct'] - 5.0) < 0.01

        # Faixa 8-12%
        assert resultado[1]['apostas'] == 1
        assert resultado[1]['lucro'] == -10.0
        assert abs(resultado[1]['roi_pct'] - (-25.0)) < 0.01

        # Faixa >12%
        assert resultado[2]['apostas'] == 1
        assert resultado[2]['lucro'] == 20.0
        assert abs(resultado[2]['roi_pct'] - 66.67) < 0.01

    def test_faixa_sem_apostas_omitida(self, tracker, db):
        """Faixa sem apostas é omitida do resultado."""
        chat_id = "456"
        # Somente faixa 5-8%
        _inserir_aposta(db, chat_id, ev_alerta=0.06, valor_apostado=100, lucro=10, status="ganhou")

        resultado = tracker.get_resumo_por_faixa_ev(chat_id)

        assert len(resultado) == 1
        assert resultado[0]['faixa'] == '5-8%'

    def test_ev_alerta_null_ignorado(self, tracker, db):
        """ev_alerta NULL é ignorado no cálculo."""
        chat_id = "789"
        # Aposta com ev_alerta NULL
        _inserir_aposta(db, chat_id, ev_alerta=None, valor_apostado=50, lucro=5, status="ganhou")
        # Aposta válida
        _inserir_aposta(db, chat_id, ev_alerta=0.10, valor_apostado=100, lucro=15, status="ganhou")

        resultado = tracker.get_resumo_por_faixa_ev(chat_id)

        assert len(resultado) == 1
        assert resultado[0]['faixa'] == '8-12%'
        assert resultado[0]['apostas'] == 1

    def test_status_pendente_e_expirado_nao_entram(self, tracker, db):
        """Apostas com status pendente ou expirado não entram no cálculo."""
        chat_id = "101"
        # Pendente — não deve contar
        _inserir_aposta(db, chat_id, ev_alerta=0.06, valor_apostado=50, lucro=0, status="pendente")
        # Expirado — não deve contar
        _inserir_aposta(db, chat_id, ev_alerta=0.09, valor_apostado=40, lucro=0, status="expirado")
        # Pulei — não deve contar
        _inserir_aposta(db, chat_id, ev_alerta=0.13, valor_apostado=30, lucro=0, status="pulei")

        resultado = tracker.get_resumo_por_faixa_ev(chat_id)

        assert resultado == []

    def test_roi_negativo_representado_corretamente(self, tracker, db):
        """ROI negativo é representado corretamente."""
        chat_id = "202"
        _inserir_aposta(db, chat_id, ev_alerta=0.06, valor_apostado=100, lucro=-30, status="perdeu")
        _inserir_aposta(db, chat_id, ev_alerta=0.07, valor_apostado=100, lucro=-20, status="perdeu")

        resultado = tracker.get_resumo_por_faixa_ev(chat_id)

        assert len(resultado) == 1
        assert resultado[0]['faixa'] == '5-8%'
        assert resultado[0]['lucro'] == -50.0
        assert abs(resultado[0]['roi_pct'] - (-25.0)) < 0.01
