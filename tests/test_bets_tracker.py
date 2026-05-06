"""
Testes do módulo bets_tracker.py — Properties 1-6.
"""
import pytest
from bets_tracker import (
    calcular_lucro, gerar_alert_hash, StatusFinalError, STATUSES_FINAIS
)


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
        assert calcular_lucro(2.0, 100, "empate") == 0.0

    def test_2_7_cashout_valor_100_cashout_80(self):
        """Caso 2.7: cashout, valor=100, cashout=80 → lucro=-20.0"""
        assert calcular_lucro(2.0, 100, "cashout", 80) == -20.0

    def test_2_8_cashout_valor_100_cashout_120(self):
        """Caso 2.8: cashout, valor=100, cashout=120 → lucro=20.0"""
        assert calcular_lucro(2.0, 100, "cashout", 120) == 20.0

    def test_status_invalido_levanta_value_error(self):
        """Status inválido deve levantar ValueError."""
        with pytest.raises(ValueError):
            calcular_lucro(2.0, 100, "invalido")

    def test_cashout_sem_valor_levanta_value_error(self):
        """Cashout sem valor_cashout deve levantar ValueError."""
        with pytest.raises(ValueError):
            calcular_lucro(2.0, 100, "cashout", None)
