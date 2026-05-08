"""
Testes unitários para _parse_valor_odd em bot_listener.py
Validates: Requirements 4.2, 4.3, 4.4
"""
import pytest

from src.bot.bot_listener import _parse_valor_odd


class TestParseValorOdd:
    """Testes para _parse_valor_odd: parsing de input 'VALOR' ou 'VALOR ODD'."""

    def test_valor_e_odd_validos(self):
        """Req 4.2: '50 2.15' → (50.0, 2.15)."""
        assert _parse_valor_odd("50 2.15") == (50.0, 2.15)

    def test_apenas_valor(self):
        """Req 4.3: '50' → (50.0, None) — odd opcional."""
        assert _parse_valor_odd("50") == (50.0, None)

    def test_virgula_como_decimal(self):
        """Req 4.4: '50,5 2,15' → (50.5, 2.15) — aceita vírgula."""
        assert _parse_valor_odd("50,5 2,15") == (50.5, 2.15)

    def test_valor_invalido(self):
        """Req 4.2: 'abc' → (None, None) — texto não numérico."""
        assert _parse_valor_odd("abc") == (None, None)

    def test_odd_abaixo_minimo(self):
        """Req 4.4: '50 0.5' → (None, None) — odd < 1.01 é inválida."""
        assert _parse_valor_odd("50 0.5") == (None, None)

    def test_string_vazia(self):
        """Req 4.2: '' → (None, None) — input vazio."""
        assert _parse_valor_odd("") == (None, None)

    def test_partes_extras(self):
        """Req 4.2: '50 2.15 extra' → (None, None) — mais de 2 partes."""
        assert _parse_valor_odd("50 2.15 extra") == (None, None)
