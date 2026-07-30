"""Testes de utilitários e funções auxiliares do app.py."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app

class TestAppUtils(unittest.TestCase):
    def test_num_br_happy_path(self):
        """Testa o caminho feliz da formatação _num_br."""
        self.assertEqual(app._num_br(10.0), "10,0")
        self.assertEqual(app._num_br(10.55, casas=1), "10,6") # 10.55 rounded to 1 decimal is 10.6 due to float representation in Python (10.55 * 10 is 105.5, rounded to nearest even might be interesting, but here it's format specifier)
        self.assertEqual(app._num_br(10.51, casas=1), "10,5")
        self.assertEqual(app._num_br(10, casas=0), "10")
        self.assertEqual(app._num_br(0), "0,0")
        self.assertEqual(app._num_br(1000.5), "1000,5")

    def test_num_br_invalid_type(self):
        """Testa o _num_br com tipos inválidos (erro e retorno string)."""
        # Strings que não podem ser convertidas para float (ValueError)
        self.assertEqual(app._num_br("abc"), "abc")
        self.assertEqual(app._num_br(""), "")

        # Tipos inválidos (TypeError)
        self.assertEqual(app._num_br([1, 2]), "[1, 2]")
        self.assertEqual(app._num_br(None), "None")
        self.assertEqual(app._num_br({"a": 1}), "{'a': 1}")

if __name__ == "__main__":
    unittest.main()
