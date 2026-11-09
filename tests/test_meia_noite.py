import unittest
from datetime import datetime, timedelta

from conftest import MARGEM, segundos_ate_passar_a_meia_noite


class TestEsperaDaMeiaNoite(unittest.TestCase):
    def test_longe_da_meia_noite_nao_espera(self):
        self.assertEqual(segundos_ate_passar_a_meia_noite(datetime(2026, 11, 8, 12, 0)), 0.0)

    def test_logo_antes_da_margem_nao_espera(self):
        agora = datetime(2026, 11, 9) - MARGEM - timedelta(seconds=1)
        self.assertEqual(segundos_ate_passar_a_meia_noite(agora), 0.0)

    def test_dentro_da_margem_espera_ate_depois_da_meia_noite(self):
        agora = datetime(2026, 11, 8, 23, 58, 23)      # o horário em que o CI do #695 começou
        espera = segundos_ate_passar_a_meia_noite(agora)
        self.assertGreater(espera, 97)                  # 1m37s até 00:00
        self.assertEqual((agora + timedelta(seconds=espera)).date(), datetime(2026, 11, 9).date())

    def test_depois_da_meia_noite_nao_espera(self):
        self.assertEqual(segundos_ate_passar_a_meia_noite(datetime(2026, 11, 9, 0, 3)), 0.0)


if __name__ == "__main__":
    unittest.main()
