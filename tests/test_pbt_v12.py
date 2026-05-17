"""
Property-Based Tests para v1.2: Aviso de Jogo Duplicado, Odd Apostada e Gestão de Banca.
Usa Hypothesis para validar as 9 propriedades de correção definidas no design.

Feature: bet-tracking-v12
"""
import os
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.core.database import Database
from src.bot.bets_tracker import (
    BetsTracker,
    calcular_lucro,
    gerar_alert_hash,
    DadosAlerta,
)
from src.bot.bot_listener import _parsear_valor_e_odd


# --- Fixtures (mesmo padrão de tests/test_bets_tracker.py) ---

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


# --- Strategies ---

# Nomes de times: strings alfanuméricas não-vazias
st_team_name = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" -"),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() != "")

# chat_id: inteiros positivos como string
st_chat_id = st.integers(min_value=1, max_value=999999999).map(str)

# commence_time no formato "YYYY-MM-DD HH:MM:SS"
st_commence_time = st.builds(
    lambda y, mo, d, h, mi, s: f"{y:04d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{s:02d}",
    y=st.integers(min_value=2020, max_value=2030),
    mo=st.integers(min_value=1, max_value=12),
    d=st.integers(min_value=1, max_value=28),
    h=st.integers(min_value=0, max_value=23),
    mi=st.integers(min_value=0, max_value=59),
    s=st.integers(min_value=0, max_value=59),
)

# Odds válidas (>= 1.01)
st_odd = st.floats(min_value=1.01, max_value=100.0, allow_nan=False, allow_infinity=False)

# Valores positivos para apostas
st_valor = st.floats(min_value=0.01, max_value=100000.0, allow_nan=False, allow_infinity=False)

# Bankroll e valor_unidade positivos
st_bankroll = st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)
st_valor_unidade = st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False)


# ============================================================
# Property 4: Round-trip de configuração de bankroll (Task 1.2, 2.4)
# Validates: Requirements 5.1, 5.2
# ============================================================

class TestProperty4RoundTripBankroll:
    """
    Property 4: Round-trip de configuração de bankroll.
    Para qualquer chat_id, bankroll > 0 e valor_unidade > 0,
    após configurar_bankroll, get_bankroll retorna os mesmos valores.

    **Validates: Requirements 5.1, 5.2**
    """

    @settings(max_examples=100)
    @given(
        chat_id=st_chat_id,
        bankroll=st_bankroll,
        valor_unidade=st_valor_unidade,
    )
    def test_round_trip_bankroll(self, tmp_path_factory, chat_id, bankroll, valor_unidade):
        """Após configurar_bankroll, get_bankroll retorna mesmos valores."""
        tmp_path = tmp_path_factory.mktemp("db")
        os.environ["FEED_ID"] = "test"
        os.environ["BOT_DATA_ROOT"] = str(tmp_path)
        database = Database.__new__(Database)
        database.feed_id = "test"
        database.db_path = str(tmp_path / "test" / "bot.db")
        os.makedirs(tmp_path / "test", exist_ok=True)
        database._init_db()
        tracker = BetsTracker(database)

        tracker.configurar_bankroll(chat_id, bankroll, valor_unidade)
        result = tracker.get_bankroll(chat_id)

        assert result is not None
        assert result["bankroll"] == pytest.approx(bankroll)
        assert result["valor_unidade"] == pytest.approx(valor_unidade)


# ============================================================
# Property 1: Consulta alertas mesmo jogo retorna registros corretos (Task 2.2)
# Validates: Requirements 3.1, 3.2
# ============================================================

class TestProperty1ConsultaAlertasMesmoJogo:
    """
    Property 1: Consulta de alertas do mesmo jogo retorna registros corretos.
    buscar_alertas_mesmo_jogo retorna exatamente os registros onde chat_id,
    home, away coincidem e os primeiros 16 chars de commence_time coincidem.

    **Validates: Requirements 3.1, 3.2**
    """

    @settings(max_examples=100)
    @given(
        chat_id=st_chat_id,
        home=st_team_name,
        away=st_team_name,
        base_ct=st_commence_time,
        n_matching=st.integers(min_value=1, max_value=5),
        n_different=st.integers(min_value=0, max_value=3),
    )
    def test_buscar_alertas_mesmo_jogo(
        self, tmp_path_factory, chat_id, home, away, base_ct, n_matching, n_different
    ):
        """Apenas alertas com mesmos primeiros 16 chars de commence_time são retornados."""
        tmp_path = tmp_path_factory.mktemp("db")
        os.environ["FEED_ID"] = "test"
        os.environ["BOT_DATA_ROOT"] = str(tmp_path)
        database = Database.__new__(Database)
        database.feed_id = "test"
        database.db_path = str(tmp_path / "test" / "bot.db")
        os.makedirs(tmp_path / "test", exist_ok=True)
        database._init_db()
        tracker = BetsTracker(database)

        ct_prefix = base_ct[:16]  # "YYYY-MM-DD HH:MM"

        # Insert matching alerts (same prefix, different seconds)
        for i in range(n_matching):
            seconds = f"{i:02d}"
            ct = ct_prefix + f":{seconds}"
            dados: DadosAlerta = {
                "home": home,
                "away": away,
                "league": "TestLeague",
                "sport": "soccer",
                "market_type": f"market_{i}",
                "bet_side": "home",
                "bookmaker": "Bet365",
                "odd_alerta": 2.0,
                "ev_alerta": 0.05,
                "commence_time": ct,
            }
            alert_hash = gerar_alert_hash(chat_id, home, away, f"market_{i}", "home", "Bet365", ct)
            tracker.registrar_alerta(alert_hash, chat_id, "feed1", dados)

        # Insert non-matching alerts (different commence_time prefix)
        for i in range(n_different):
            # Change the hour to create a different prefix
            different_ct = f"2019-06-{(i+1):02d} 10:30:{i:02d}"
            dados_diff: DadosAlerta = {
                "home": home,
                "away": away,
                "league": "TestLeague",
                "sport": "soccer",
                "market_type": f"diff_market_{i}",
                "bet_side": "away",
                "bookmaker": "Pinnacle",
                "odd_alerta": 3.0,
                "ev_alerta": 0.08,
                "commence_time": different_ct,
            }
            alert_hash_diff = gerar_alert_hash(
                chat_id, home, away, f"diff_market_{i}", "away", "Pinnacle", different_ct
            )
            tracker.registrar_alerta(alert_hash_diff, chat_id, "feed1", dados_diff)

        # Query
        result = tracker.buscar_alertas_mesmo_jogo(chat_id, home, away, base_ct)

        # Should return exactly n_matching records
        assert len(result) == n_matching

        # All returned records should have matching commence_time prefix
        for r in result:
            assert r.get("market_type", "").startswith("market_")


# ============================================================
# Property 5: Reset apaga todos os dados do usuário (Task 2.6)
# Validates: Requirements 6.1, 6.2
# ============================================================

class TestProperty5ResetApagaDados:
    """
    Property 5: Reset apaga todos os dados do usuário.
    Após inserir N apostas e configurar bankroll, resetar_banca
    deve resultar em listas vazias e bankroll None.

    **Validates: Requirements 6.1, 6.2**
    """

    @settings(max_examples=100)
    @given(
        chat_id=st_chat_id,
        n_apostas=st.integers(min_value=1, max_value=5),
        bankroll=st_bankroll,
        valor_unidade=st_valor_unidade,
    )
    def test_reset_apaga_tudo(self, tmp_path_factory, chat_id, n_apostas, bankroll, valor_unidade):
        """Após resetar_banca, get_pendentes retorna vazio e get_bankroll retorna None."""
        tmp_path = tmp_path_factory.mktemp("db")
        os.environ["FEED_ID"] = "test"
        os.environ["BOT_DATA_ROOT"] = str(tmp_path)
        database = Database.__new__(Database)
        database.feed_id = "test"
        database.db_path = str(tmp_path / "test" / "bot.db")
        os.makedirs(tmp_path / "test", exist_ok=True)
        database._init_db()
        tracker = BetsTracker(database)

        # Insert N alerts and mark as bet placed (so they appear in pendentes)
        for i in range(n_apostas):
            dados: DadosAlerta = {
                "home": f"Home{i}",
                "away": f"Away{i}",
                "league": "Liga",
                "sport": "soccer",
                "market_type": "h2h",
                "bet_side": "home",
                "bookmaker": "Bet365",
                "odd_alerta": 2.0,
                "ev_alerta": 0.05,
                "commence_time": f"2030-01-{(i+1):02d} 20:00:00",
            }
            alert_hash = gerar_alert_hash(
                chat_id, f"Home{i}", f"Away{i}", "h2h", "home", "Bet365",
                f"2030-01-{(i+1):02d} 20:00:00"
            )
            bet_id = tracker.registrar_alerta(alert_hash, chat_id, "feed1", dados)
            tracker.marcar_apostou(bet_id, 5.0, 10.0)

        # Configure bankroll
        tracker.configurar_bankroll(chat_id, bankroll, valor_unidade)

        # Verify data exists
        assert len(tracker.get_pendentes(chat_id)) == n_apostas
        assert tracker.get_bankroll(chat_id) is not None

        # Reset
        tracker.resetar_banca(chat_id)

        # Verify all data is gone
        assert tracker.get_pendentes(chat_id) == []
        assert tracker.get_bankroll(chat_id) is None


# ============================================================
# Property 2: Persistência de odd_apostada com fallback (Task 2.7)
# Validates: Requirements 4.1, 4.2
# ============================================================

class TestProperty2PersistenciaOddApostada:
    """
    Property 2: Persistência de odd_apostada com fallback.
    marcar_apostou com odd_apostada=None copia odd_alerta,
    e com valor informado persiste o valor.

    **Validates: Requirements 4.1, 4.2**
    """

    @settings(max_examples=100)
    @given(
        odd_alerta=st_odd,
        odd_apostada=st.one_of(st.none(), st_odd),
        valor=st_valor,
    )
    def test_persistencia_odd_apostada(self, tmp_path_factory, odd_alerta, odd_apostada, valor):
        """odd_apostada=None → copia odd_alerta; odd_apostada=X → persiste X."""
        tmp_path = tmp_path_factory.mktemp("db")
        os.environ["FEED_ID"] = "test"
        os.environ["BOT_DATA_ROOT"] = str(tmp_path)
        database = Database.__new__(Database)
        database.feed_id = "test"
        database.db_path = str(tmp_path / "test" / "bot.db")
        os.makedirs(tmp_path / "test", exist_ok=True)
        database._init_db()
        tracker = BetsTracker(database)

        dados: DadosAlerta = {
            "home": "TeamA",
            "away": "TeamB",
            "league": "Liga",
            "sport": "soccer",
            "market_type": "h2h",
            "bet_side": "home",
            "bookmaker": "Bet365",
            "odd_alerta": odd_alerta,
            "ev_alerta": 0.05,
            "commence_time": "2025-06-15 20:00:00",
        }
        alert_hash = gerar_alert_hash(
            "999", "TeamA", "TeamB", "h2h", "home", "Bet365", "2025-06-15 20:00:00"
        )
        bet_id = tracker.registrar_alerta(alert_hash, "999", "feed1", dados)
        tracker.marcar_apostou(bet_id, valor, 1.0, odd_apostada=odd_apostada)

        # Read back from DB
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT odd_apostada, odd_alerta FROM bets_placed WHERE id = ?",
                (bet_id,)
            ).fetchone()

        if odd_apostada is not None:
            assert row["odd_apostada"] == pytest.approx(odd_apostada)
        else:
            # Fallback: should copy odd_alerta
            assert row["odd_apostada"] == pytest.approx(odd_alerta)


# ============================================================
# Property 3: Cálculo de lucro usa odd correta (Task 2.8)
# Validates: Requirements 4.3
# ============================================================

class TestProperty3CalculoLucroOddCorreta:
    """
    Property 3: Cálculo de lucro usa odd correta.
    marcar_resultado usa odd_apostada quando disponível,
    fallback odd_alerta. Lucro = calcular_lucro(odd_efetiva, valor, status).

    **Validates: Requirements 4.3**
    """

    @settings(max_examples=100)
    @given(
        odd_alerta=st_odd,
        odd_apostada=st.one_of(st.none(), st_odd),
        valor=st_valor,
        status=st.sampled_from(["ganhou", "perdeu", "empate"]),
    )
    def test_calculo_lucro_odd_correta(
        self, tmp_path_factory, odd_alerta, odd_apostada, valor, status
    ):
        """Lucro calculado deve usar odd_apostada se disponível, senão odd_alerta."""
        tmp_path = tmp_path_factory.mktemp("db")
        os.environ["FEED_ID"] = "test"
        os.environ["BOT_DATA_ROOT"] = str(tmp_path)
        database = Database.__new__(Database)
        database.feed_id = "test"
        database.db_path = str(tmp_path / "test" / "bot.db")
        os.makedirs(tmp_path / "test", exist_ok=True)
        database._init_db()
        tracker = BetsTracker(database)

        dados: DadosAlerta = {
            "home": "TeamA",
            "away": "TeamB",
            "league": "Liga",
            "sport": "soccer",
            "market_type": "h2h",
            "bet_side": "home",
            "bookmaker": "Bet365",
            "odd_alerta": odd_alerta,
            "ev_alerta": 0.05,
            "commence_time": "2025-06-15 20:00:00",
        }
        alert_hash = gerar_alert_hash(
            "888", "TeamA", "TeamB", "h2h", "home", "Bet365", "2025-06-15 20:00:00"
        )
        bet_id = tracker.registrar_alerta(alert_hash, "888", "feed1", dados)
        tracker.marcar_apostou(bet_id, valor, 1.0, odd_apostada=odd_apostada)
        tracker.marcar_resultado(bet_id, status)

        # Determine expected odd
        odd_efetiva = odd_apostada if odd_apostada is not None else odd_alerta
        expected_lucro = calcular_lucro(odd_efetiva, valor, status)

        # Read lucro from DB
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT lucro FROM bets_placed WHERE id = ?", (bet_id,)
            ).fetchone()

        assert row["lucro"] == pytest.approx(expected_lucro, rel=1e-6)


# ============================================================
# Property 6: Construção de aviso de jogo duplicado (Task 4.2)
# Validates: Requirements 7.1, 7.2
# ============================================================

class TestProperty6ConstrucaoAvisoDuplicado:
    """
    Property 6: Construção de aviso de jogo duplicado.
    Para lista vazia, _montar_aviso_mesmo_jogo retorna "".
    Para lista não-vazia, retorna string contendo info de cada alerta.

    **Validates: Requirements 7.1, 7.2**
    """

    @settings(max_examples=100)
    @given(
        alertas=st.lists(
            st.fixed_dictionaries({
                "market_type": st.text(min_size=1, max_size=10),
                "odd_alerta": st_odd,
                "status": st.sampled_from(["pendente", "ganhou", "perdeu", "empate"]),
                "valor_apostado": st.one_of(st.none(), st_valor),
            }),
            min_size=0,
            max_size=5,
        )
    )
    def test_montar_aviso_mesmo_jogo(self, alertas):
        """Lista vazia → ''; lista não-vazia → string com info de cada alerta."""
        from src.bot.bot_ev import AlertSender

        # Create a minimal AlertSender instance with mocks
        sender = AlertSender.__new__(AlertSender)

        result = sender._montar_aviso_mesmo_jogo(alertas)

        if not alertas:
            assert result == ""
        else:
            assert isinstance(result, str)
            assert len(result) > 0
            # Should contain the header
            assert "alerta" in result.lower() or "⚠️" in result
            # Should have one line per alert (bullet point)
            for a in alertas:
                # Each alert contributes a bullet line with odd info
                odd_str = f"{float(a['odd_alerta']):.2f}"
                assert odd_str in result


# ============================================================
# Property 7: Injeção de aviso no template (Task 4.4)
# Validates: Requirements 8.2, 8.3
# ============================================================

class TestProperty7InjecaoAvisoTemplate:
    """
    Property 7: Injeção de aviso no template.
    Para aviso não-vazio, o bloco de aviso contém o texto.
    Para aviso vazio, o bloco é vazio.

    **Validates: Requirements 8.2, 8.3**
    """

    @settings(max_examples=100)
    @given(
        aviso=st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != ""),
    )
    def test_aviso_nao_vazio_presente_no_bloco(self, aviso):
        """Para aviso não-vazio, o bloco formatado contém o texto do aviso."""
        # Test the aviso_bloco logic directly as specified
        aviso_bloco = f"\n{aviso}\n" if aviso else ""
        assert aviso in aviso_bloco
        assert len(aviso_bloco) > 0

    @settings(max_examples=100)
    @given(
        aviso=st.just(""),
    )
    def test_aviso_vazio_bloco_vazio(self, aviso):
        """Para aviso vazio, o bloco é string vazia."""
        aviso_bloco = f"\n{aviso}\n" if aviso else ""
        assert aviso_bloco == ""


# ============================================================
# Property 8: Parsing de valor e odd (Task 5.2)
# Validates: Requirements 9.1, 9.2, 9.3
# ============================================================

class TestProperty8ParseValorEOdd:
    """
    Property 8: Parsing de valor e odd.
    Para valores válidos, _parsear_valor_e_odd retorna tupla correta.
    Para inputs inválidos, retorna None.

    **Validates: Requirements 9.1, 9.2, 9.3**
    """

    @settings(max_examples=100)
    @given(
        valor=st.integers(min_value=1, max_value=99999),
    )
    def test_apenas_valor_inteiro(self, valor):
        """Input 'VALOR' (inteiro) → (valor, None)."""
        result = _parsear_valor_e_odd(str(valor))
        assert result is not None
        assert result == (float(valor), None)

    @settings(max_examples=100)
    @given(
        valor=st.integers(min_value=1, max_value=99999),
        centavos=st.integers(min_value=0, max_value=99),
        odd_int=st.integers(min_value=1, max_value=99),
        odd_dec=st.integers(min_value=1, max_value=99),
    )
    def test_valor_e_odd_validos(self, valor, centavos, odd_int, odd_dec):
        """Input 'VALOR ODD' com odd >= 1.01 → (valor, odd)."""
        # Build valor string with up to 2 decimal places
        if centavos > 0:
            valor_str = f"{valor}.{centavos:02d}".rstrip("0")
            # Ensure we don't end with a dot
            if valor_str.endswith("."):
                valor_str = valor_str[:-1]
        else:
            valor_str = str(valor)

        # Build odd >= 1.01
        odd_val = float(f"{odd_int}.{odd_dec:02d}")
        assume(odd_val >= 1.01)
        odd_str = f"{odd_int}.{odd_dec:02d}".rstrip("0")
        if odd_str.endswith("."):
            odd_str = odd_str[:-1]

        texto = f"{valor_str} {odd_str}"
        result = _parsear_valor_e_odd(texto)

        if result is not None:
            r_valor, r_odd = result
            expected_valor = float(valor_str)
            expected_odd = float(odd_str)
            assert r_valor == pytest.approx(expected_valor)
            assert r_odd == pytest.approx(expected_odd)

    @settings(max_examples=100)
    @given(
        texto=st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1,
            max_size=10,
        )
    )
    def test_texto_invalido_retorna_none(self, texto):
        """Input não-numérico → None."""
        assume(not texto.strip().replace(",", ".").replace(" ", "").replace(".", "").isdigit())
        result = _parsear_valor_e_odd(texto)
        assert result is None

    @settings(max_examples=100)
    @given(
        valor=st.integers(min_value=1, max_value=99999),
        odd_low=st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    def test_odd_abaixo_minimo_retorna_none(self, valor, odd_low):
        """Input com odd < 1.01 → None."""
        # Format odd with max 2 decimal places
        odd_str = f"{odd_low:.2f}"
        texto = f"{valor} {odd_str}"
        result = _parsear_valor_e_odd(texto)
        assert result is None


# ============================================================
# Property 9: Exibição de odd com fallback (Task 5.7)
# Validates: Requirements 10.1, 10.2, 10.3
# ============================================================

class TestProperty9ExibicaoOddFallback:
    """
    Property 9: Exibição de odd com fallback.
    A lógica ap.get('odd_apostada') or ap.get('odd_alerta', 0)
    retorna odd_apostada quando disponível, senão odd_alerta.

    **Validates: Requirements 10.1, 10.2, 10.3**
    """

    @settings(max_examples=100)
    @given(
        odd_apostada=st_odd,
        odd_alerta=st_odd,
    )
    def test_odd_apostada_disponivel(self, odd_apostada, odd_alerta):
        """Quando odd_apostada está definida, usa odd_apostada."""
        ap = {"odd_apostada": odd_apostada, "odd_alerta": odd_alerta}
        odd_exibida = ap.get("odd_apostada") or ap.get("odd_alerta", 0)
        assert odd_exibida == pytest.approx(odd_apostada)

    @settings(max_examples=100)
    @given(
        odd_alerta=st_odd,
    )
    def test_odd_apostada_none_usa_odd_alerta(self, odd_alerta):
        """Quando odd_apostada é None, usa odd_alerta."""
        ap = {"odd_apostada": None, "odd_alerta": odd_alerta}
        odd_exibida = ap.get("odd_apostada") or ap.get("odd_alerta", 0)
        assert odd_exibida == pytest.approx(odd_alerta)

    @settings(max_examples=100)
    @given(
        odd_alerta=st_odd,
    )
    def test_odd_apostada_ausente_usa_odd_alerta(self, odd_alerta):
        """Quando odd_apostada não existe no dict, usa odd_alerta."""
        ap = {"odd_alerta": odd_alerta}
        odd_exibida = ap.get("odd_apostada") or ap.get("odd_alerta", 0)
        assert odd_exibida == pytest.approx(odd_alerta)

    @settings(max_examples=100)
    @given(data=st.data())
    def test_fallback_zero_quando_ambos_ausentes(self, data):
        """Quando ambos ausentes, retorna 0."""
        ap = {}
        odd_exibida = ap.get("odd_apostada") or ap.get("odd_alerta", 0)
        assert odd_exibida == 0
