"""
Testes para a exibição de odd mínima nos alertas de EV.

Cobre:
- Odd mínima calculada corretamente para valores válidos
- Linha omitida quando odd_alerta <= 0
- Linha omitida quando (1 + ev_alerta) <= 0
- Usa ev_faixa_min do chat quando configurado, senão default 0.05
"""
import pytest
from unittest.mock import patch, MagicMock

from src.bot.bot_core import calcular_odd_minima


# ---------------------------------------------------------------------------
# Testes unitários de calcular_odd_minima (lógica pura)
# ---------------------------------------------------------------------------

class TestCalcularOddMinima:

    def test_calculo_correto_valores_validos(self):
        """
        Dado odd=2.0 e ev=0.10 (10%):
        prob_real = (1 + 0.10) / 2.0 = 0.55
        odd_minima(ev=0.05, prob=0.55) = (0.05 + 1) / 0.55 ≈ 1.909
        """
        odd_alerta = 2.0
        ev_alerta = 0.10
        ev_minimo = 0.05
        prob_real = (1 + ev_alerta) / odd_alerta
        resultado = calcular_odd_minima(ev_minimo, prob_real)
        assert resultado == pytest.approx(1.909, rel=1e-3)

    def test_calculo_com_ev_minimo_maior(self):
        """
        odd=3.0, ev=0.15, ev_minimo=0.08
        prob_real = 1.15 / 3.0 ≈ 0.3833
        odd_minima = 1.08 / 0.3833 ≈ 2.817
        """
        odd_alerta = 3.0
        ev_alerta = 0.15
        ev_minimo = 0.08
        prob_real = (1 + ev_alerta) / odd_alerta
        resultado = calcular_odd_minima(ev_minimo, prob_real)
        assert resultado == pytest.approx(2.817, rel=1e-3)

    def test_prob_zero_retorna_none(self):
        """prob_real = 0 deve retornar None (sem divisão por zero)."""
        assert calcular_odd_minima(0.05, 0) is None

    def test_prob_negativa_retorna_none(self):
        """prob_real negativa deve retornar None."""
        assert calcular_odd_minima(0.05, -0.5) is None


# ---------------------------------------------------------------------------
# Testes da lógica de _calcular_odd_minima no AlertSender
# ---------------------------------------------------------------------------

class TestAlertSenderOddMinima:
    """
    Testa o método _calcular_odd_minima do AlertSender sem instanciar
    o bot completo (evita conexão Telegram e banco real).
    """

    def _make_sender(self, ev_faixa_min: float = 0.05):
        """Cria AlertSender mockado com ev_faixa_min configurável."""
        from src.bot.bot_ev import AlertSender
        sender = object.__new__(AlertSender)
        # Mock _get_ev_minimo para retornar valor controlado
        sender._get_ev_minimo = MagicMock(return_value=ev_faixa_min)
        return sender

    def test_odd_minima_valida(self):
        """Odd e EV válidos → retorna float."""
        sender = self._make_sender(ev_faixa_min=0.05)
        aposta = {"bet365_odds": 2.0, "ev": 0.10}
        resultado = sender._calcular_odd_minima(aposta, "123")
        assert resultado is not None
        assert isinstance(resultado, float)
        assert resultado == pytest.approx(1.909, rel=1e-3)

    def test_odd_alerta_zero_retorna_none(self):
        """odd_alerta = 0 → deve retornar None."""
        sender = self._make_sender()
        aposta = {"bet365_odds": 0, "ev": 0.10}
        assert sender._calcular_odd_minima(aposta, "123") is None

    def test_odd_alerta_negativa_retorna_none(self):
        """odd_alerta negativa → deve retornar None."""
        sender = self._make_sender()
        aposta = {"bet365_odds": -1.5, "ev": 0.10}
        assert sender._calcular_odd_minima(aposta, "123") is None

    def test_ev_minus_one_retorna_none(self):
        """ev_alerta = -1 → (1 + ev) = 0, divisão por zero → None."""
        sender = self._make_sender()
        aposta = {"bet365_odds": 2.0, "ev": -1.0}
        assert sender._calcular_odd_minima(aposta, "123") is None

    def test_ev_menor_que_minus_one_retorna_none(self):
        """ev_alerta < -1 → (1 + ev) < 0, inválido → None."""
        sender = self._make_sender()
        aposta = {"bet365_odds": 2.0, "ev": -1.5}
        assert sender._calcular_odd_minima(aposta, "123") is None

    def test_usa_ev_faixa_min_do_chat(self):
        """Usa ev_faixa_min=0.08 em vez do default 0.05."""
        sender = self._make_sender(ev_faixa_min=0.08)
        aposta = {"bet365_odds": 3.0, "ev": 0.15}
        resultado = sender._calcular_odd_minima(aposta, "456")
        assert resultado == pytest.approx(2.817, rel=1e-3)
        sender._get_ev_minimo.assert_called_once_with("456")

    def test_default_ev_quando_chat_id_vazio(self):
        """
        Sem chat_id, _calcular_odd_minima usa o default 0.05 e retorna um float.
        A proteção para omitir a linha está nos formatadores (if chat_id else None),
        não neste método.
        """
        sender = self._make_sender(ev_faixa_min=0.05)
        aposta = {"bet365_odds": 2.0, "ev": 0.10}
        resultado = sender._calcular_odd_minima(aposta, "")
        # chat_id vazio ainda chama _get_ev_minimo com "" e usa default 0.05
        assert resultado == pytest.approx(1.909, rel=1e-3)


# ---------------------------------------------------------------------------
# Teste do _get_ev_minimo com fallback
# ---------------------------------------------------------------------------

class TestGetEvMinimo:

    def _make_sender(self):
        from src.bot.bot_ev import AlertSender
        return object.__new__(AlertSender)

    def test_retorna_default_quando_db_falha(self):
        """Se get_db() lança exceção, retorna 0.05."""
        sender = self._make_sender()
        with patch("src.bot.bot_ev.get_db", side_effect=Exception("db error")):
            assert sender._get_ev_minimo("999") == pytest.approx(0.05)

    def test_retorna_default_quando_usuario_nao_existe(self):
        """Se usuário não encontrado no banco, retorna 0.05."""
        sender = self._make_sender()
        mock_db = MagicMock()
        mock_db.get_user_complete.return_value = None
        with patch("src.bot.bot_ev.get_db", return_value=mock_db):
            assert sender._get_ev_minimo("999") == pytest.approx(0.05)

    def test_retorna_valor_do_banco(self):
        """Se usuário tem ev_faixa_min configurado, retorna esse valor."""
        sender = self._make_sender()
        mock_db = MagicMock()
        mock_db.get_user_complete.return_value = {"ev_faixa_min": 0.08}
        with patch("src.bot.bot_ev.get_db", return_value=mock_db):
            assert sender._get_ev_minimo("123") == pytest.approx(0.08)

    def test_retorna_default_quando_ev_faixa_min_none(self):
        """Se ev_faixa_min é None no banco, retorna 0.05."""
        sender = self._make_sender()
        mock_db = MagicMock()
        mock_db.get_user_complete.return_value = {"ev_faixa_min": None}
        with patch("src.bot.bot_ev.get_db", return_value=mock_db):
            assert sender._get_ev_minimo("123") == pytest.approx(0.05)
