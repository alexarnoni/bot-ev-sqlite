"""
Teste exploratório da condição do bug: Nome do Mercado Incorreto no Aviso de Duplicata.

**Validates: Requirements 1.1, 1.2**

Bug: `_montar_aviso_mesmo_jogo()` chama `formatar_market_name(a.get('market_type', ''), aposta=a)`
mas o dict `a` retornado por `buscar_alertas_mesmo_jogo()` não contém os campos auxiliares
necessários (market.hdp, betSide, event.sport, event.home, event.away) para formatação correta.

Resultado: mercados complexos (totals, handicap) aparecem com nome genérico/cru
ao invés do nome formatado correto (ex: "Totals" ao invés de "Mais de 2.5 Gols").

ESTE TESTE É ESPERADO FALHAR NO CÓDIGO NÃO CORRIGIDO — a falha confirma que o bug existe.
"""
import os
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from src.core.database import Database
from src.bot.bets_tracker import BetsTracker, gerar_alert_hash, DadosAlerta
from src.bot.bot_ev import AlertSender
from src.utils.formatadores import formatar_market_name


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


# --- Teste exploratório do bug ---

class TestBugAvisoMercadoIncorreto:
    """
    Property 1: Bug Condition — Nome do Mercado Incorreto no Aviso de Duplicata.

    Demonstra que `_montar_aviso_mesmo_jogo` produz nomes de mercado incorretos
    porque `buscar_alertas_mesmo_jogo` retorna dicts sem campos auxiliares.
    """

    def test_totals_market_nome_incorreto(self, tracker, db):
        """
        Bug Condition: mercado totals com hdp=2.5 deve exibir "Mais de 2.5 Gols"
        no aviso, mas exibe nome genérico porque o dict não tem campos auxiliares.

        **Validates: Requirements 1.1, 1.2**
        """
        chat_id = "12345"
        home = "Flamengo"
        away = "Palmeiras"
        commence_time = "2025-01-15 20:00:00"

        # Dados completos do alerta original (como chegam no enviar_alerta)
        aposta_completa = {
            "home": home,
            "away": away,
            "league": "Brasileirão",
            "sport": "soccer",
            "market_type": "totals",
            "bet_side": "over",
            "bookmaker": "Bet365",
            "bet365_odds": 1.90,
            "ev": 0.06,
            "commence_time": commence_time,
            # Campos auxiliares que formatar_market_name precisa:
            "market": {"name": "totals", "hdp": 2.5},
            "betSide": "Over",
            "event": {"sport": "soccer", "home": home, "away": away},
            "hdp": 2.5,
        }

        # O nome CORRETO que deveria aparecer no aviso
        nome_correto = formatar_market_name("totals", aposta=aposta_completa)
        # Deve ser algo como "Mais de 2.5 Gols"
        assert "2.5" in nome_correto, f"Nome correto deveria conter '2.5', got: {nome_correto}"

        # Registra o alerta no banco (como faz enviar_alerta)
        alert_hash = gerar_alert_hash(
            chat_id, home, away, "totals", "over", "Bet365", commence_time
        )
        dados_alerta: DadosAlerta = {
            "home": home,
            "away": away,
            "league": "Brasileirão",
            "sport": "soccer",
            "market_type": "totals",
            "bet_side": "over",
            "bookmaker": "Bet365",
            "odd_alerta": 1.90,
            "ev_alerta": 0.06,
            "commence_time": commence_time,
        }
        bet_id = tracker.registrar_alerta(alert_hash, chat_id, "feed1", dados_alerta)

        # Salvar nome do mercado formatado (como faz enviar_alerta após a correção)
        mercado_fmt = formatar_market_name("totals", aposta=aposta_completa)
        with tracker.db.get_connection() as conn:
            conn.execute(
                "UPDATE bets_placed SET market_name_fmt = ? WHERE id = ?",
                (mercado_fmt, bet_id)
            )

        # Busca alertas anteriores (como faz _montar_aviso_mesmo_jogo)
        alertas = tracker.buscar_alertas_mesmo_jogo(chat_id, home, away, commence_time)
        assert len(alertas) > 0, "Deveria ter pelo menos 1 alerta"

        # Cria AlertSender minimal para chamar _montar_aviso_mesmo_jogo
        # Monkey-patch para evitar inicialização do Telegram Bot
        sender = AlertSender.__new__(AlertSender)
        sender._bets_tracker = tracker

        # Chama _montar_aviso_mesmo_jogo com os alertas retornados
        aviso = sender._montar_aviso_mesmo_jogo(alertas)

        # ASSERÇÃO DO BUG: o aviso deveria conter o nome formatado correto
        # (ex: "Mais de 2.5 Gols"), mas no código bugado vai conter apenas
        # algo genérico como "Totals" ou "Mais/Menos" sem o valor 2.5
        assert "2.5" in aviso, (
            f"Bug confirmado! O aviso deveria conter '2.5' (nome formatado correto: '{nome_correto}'), "
            f"mas o aviso gerado foi:\n{aviso}"
        )

    def test_handicap_market_nome_incorreto(self, tracker, db):
        """
        Bug Condition: mercado handicap com hdp=1.5 deve exibir
        "Handicap — Flamengo +1.5" no aviso, mas exibe nome genérico.

        **Validates: Requirements 1.1, 1.2**
        """
        chat_id = "12345"
        home = "Flamengo"
        away = "Palmeiras"
        commence_time = "2025-01-15 20:00:00"

        # Dados completos do alerta original
        aposta_completa = {
            "home": home,
            "away": away,
            "league": "Brasileirão",
            "sport": "soccer",
            "market_type": "spreads",
            "bet_side": "home",
            "bookmaker": "Bet365",
            "bet365_odds": 2.10,
            "ev": 0.05,
            "commence_time": commence_time,
            "market": {"name": "spreads", "hdp": 1.5},
            "betSide": "home",
            "event": {"sport": "soccer", "home": home, "away": away},
            "hdp": 1.5,
        }

        # O nome CORRETO que deveria aparecer
        nome_correto = formatar_market_name("spreads", aposta=aposta_completa)
        # Deve conter "1.5" e possivelmente "Flamengo"
        assert "1.5" in nome_correto, f"Nome correto deveria conter '1.5', got: {nome_correto}"

        # Registra o alerta
        alert_hash = gerar_alert_hash(
            chat_id, home, away, "spreads", "home", "Bet365", commence_time
        )
        dados_alerta: DadosAlerta = {
            "home": home,
            "away": away,
            "league": "Brasileirão",
            "sport": "soccer",
            "market_type": "spreads",
            "bet_side": "home",
            "bookmaker": "Bet365",
            "odd_alerta": 2.10,
            "ev_alerta": 0.05,
            "commence_time": commence_time,
        }
        bet_id = tracker.registrar_alerta(alert_hash, chat_id, "feed1", dados_alerta)

        # Salvar nome do mercado formatado (como faz enviar_alerta após a correção)
        mercado_fmt = formatar_market_name("spreads", aposta=aposta_completa)
        with tracker.db.get_connection() as conn:
            conn.execute(
                "UPDATE bets_placed SET market_name_fmt = ? WHERE id = ?",
                (mercado_fmt, bet_id)
            )

        # Busca alertas anteriores
        alertas = tracker.buscar_alertas_mesmo_jogo(chat_id, home, away, commence_time)
        assert len(alertas) > 0

        # Monta aviso
        sender = AlertSender.__new__(AlertSender)
        sender._bets_tracker = tracker
        aviso = sender._montar_aviso_mesmo_jogo(alertas)

        # ASSERÇÃO DO BUG: deveria conter "1.5" mas não vai ter
        assert "1.5" in aviso, (
            f"Bug confirmado! O aviso deveria conter '1.5' (nome formatado correto: '{nome_correto}'), "
            f"mas o aviso gerado foi:\n{aviso}"
        )

    @given(
        hdp_value=st.sampled_from([0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.5]),
        bet_side=st.sampled_from(["over", "under"]),
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pbt_totals_market_bug_condition(self, db, tracker, hdp_value, bet_side):
        """
        Property-based test: para qualquer valor de hdp em mercados totals,
        o aviso de duplicata deveria conter o valor hdp formatado, mas não contém.

        **Validates: Requirements 1.1, 1.2**
        """
        chat_id = "99999"
        home = "TimeA"
        away = "TimeB"
        commence_time = "2025-06-01 18:00:00"

        # Dados completos (como no envio original)
        aposta_completa = {
            "home": home,
            "away": away,
            "league": "Liga Teste",
            "sport": "soccer",
            "market_type": "totals",
            "bet_side": bet_side,
            "bookmaker": "Pinnacle",
            "commence_time": commence_time,
            "market": {"name": "totals", "hdp": hdp_value},
            "betSide": bet_side.title(),
            "event": {"sport": "soccer", "home": home, "away": away},
            "hdp": hdp_value,
        }

        # Nome correto que deveria aparecer
        nome_correto = formatar_market_name("totals", aposta=aposta_completa)
        hdp_str = str(hdp_value)
        # Remove trailing zero for integers (e.g., 1.0 -> "1.0" stays as is in format)
        assert hdp_str in nome_correto, (
            f"formatar_market_name com dados completos deveria conter '{hdp_str}', got: {nome_correto}"
        )

        # Registra alerta (sem campos auxiliares no banco)
        alert_hash = gerar_alert_hash(
            chat_id, home, away, "totals", bet_side, "Pinnacle", commence_time
        )
        dados_alerta: DadosAlerta = {
            "home": home,
            "away": away,
            "league": "Liga Teste",
            "sport": "soccer",
            "market_type": "totals",
            "bet_side": bet_side,
            "bookmaker": "Pinnacle",
            "odd_alerta": 1.85,
            "ev_alerta": 0.04,
            "commence_time": commence_time,
        }
        bet_id = tracker.registrar_alerta(alert_hash, chat_id, "feed1", dados_alerta)

        # Salvar nome do mercado formatado (como faz enviar_alerta após a correção)
        mercado_fmt = formatar_market_name("totals", aposta=aposta_completa)
        with tracker.db.get_connection() as conn:
            conn.execute(
                "UPDATE bets_placed SET market_name_fmt = ? WHERE id = ?",
                (mercado_fmt, bet_id)
            )

        # Busca e monta aviso
        alertas = tracker.buscar_alertas_mesmo_jogo(chat_id, home, away, commence_time)
        sender = AlertSender.__new__(AlertSender)
        sender._bets_tracker = tracker
        aviso = sender._montar_aviso_mesmo_jogo(alertas)

        # Bug condition: o aviso NÃO contém o valor hdp correto
        assert hdp_str in aviso, (
            f"Bug confirmado! Aviso deveria conter '{hdp_str}' "
            f"(nome correto: '{nome_correto}'), mas gerou:\n{aviso}"
        )
