"""services/financeiro.py — função pura, sem banco."""

import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from services.financeiro import valor_esperado_venda  # noqa: E402


class TestValorEsperadoVenda(unittest.TestCase):
    def test_multiplica_peso_por_preco(self):
        self.assertEqual(valor_esperado_venda(400.0, 12.5), 5000.0)

    def test_preco_zero_da_valor_zero(self):
        """Categoria sem preço cadastrado (`get_expected_price_kg` devolve 0.0)
        não deve gerar erro nem valor negativo — só zero, refletindo a
        ausência de dado."""
        self.assertEqual(valor_esperado_venda(400.0, 0.0), 0.0)

    def test_arredonda_para_duas_casas(self):
        self.assertEqual(valor_esperado_venda(333.333, 3.0), 1000.0)
        self.assertEqual(valor_esperado_venda(100.0, 3.333), 333.3)


if __name__ == "__main__":
    unittest.main()
