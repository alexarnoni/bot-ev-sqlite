"""
Testes unitários para o módulo bot_core.py
Validates: Requirements 9.1, 9.2
"""
import pytest

from src.bot.bot_core import definir_stake


class TestDefinirStake:
    """Testes para definir_stake: validação de odd e cálculo de stake."""

    def test_odd_none_retorna_minimo(self):
        """Req 9.1: odd=None → retorna 0.1 (stake mínima)."""
        assert definir_stake(0.05, None) == 0.1

    def test_odd_zero_retorna_minimo(self):
        """Req 9.2: odd=0 → retorna 0.1 (odd <= 0)."""
        assert definir_stake(0.05, 0) == 0.1

    def test_odd_negativa_retorna_minimo(self):
        """Req 9.2: odd=-1.5 → retorna 0.1 (odd <= 0)."""
        assert definir_stake(0.05, -1.5) == 0.1

    def test_odd_nao_numerica_retorna_minimo(self):
        """Req 9.1: odd="abc" → retorna 0.1 (TypeError/ValueError)."""
        assert definir_stake(0.05, "abc") == 0.1

    def test_odd_2_0_retorna_1_0(self):
        """odd=2.0 está no intervalo [1.50, 3.50] → stake=1.0."""
        assert definir_stake(0.05, 2.0) == 1.0

    def test_odd_5_0_retorna_0_5(self):
        """odd=5.0 está no intervalo [3.51, 8.00] → stake=0.5."""
        assert definir_stake(0.05, 5.0) == 0.5

    def test_odd_10_0_retorna_0_25(self):
        """odd=10.0 está acima de 8.00 → stake=0.25."""
        assert definir_stake(0.05, 10.0) == 0.25

    def test_odd_1_0_retorna_minimo(self):
        """odd=1.0 está abaixo de 1.50 → cai no else → stake=0.1."""
        assert definir_stake(0.05, 1.0) == 0.1
