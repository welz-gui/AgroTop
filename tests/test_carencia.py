import unittest
from datetime import date

from services.carencia import fim_da_carencia

REF = date(2026, 10, 10)


def _aplic(med_date, dias):
    return {"med_date": med_date, "withdrawal_days": dias}


class TestFimDaCarencia(unittest.TestCase):
    def test_sem_aplicacoes(self):
        self.assertIsNone(fim_da_carencia([], REF))

    def test_carencia_ativa_devolve_o_fim(self):
        # 2026-10-08 + 10 dias = 2026-10-18
        self.assertEqual(fim_da_carencia([_aplic("2026-10-08", 10)], REF), date(2026, 10, 18))

    def test_dia_antes_do_fim_ainda_e_carencia(self):
        self.assertEqual(fim_da_carencia([_aplic("2026-10-06", 5)], REF), date(2026, 10, 11))

    def test_no_dia_do_fim_o_animal_ja_esta_liberado(self):
        """Mesmo critério de `get_withdrawal_end` (fim > hoje)."""
        self.assertIsNone(fim_da_carencia([_aplic("2026-10-05", 5)], REF))

    def test_carencia_vencida(self):
        self.assertIsNone(fim_da_carencia([_aplic("2026-09-01", 21)], REF))

    def test_entre_varias_vale_a_mais_longa(self):
        aplicacoes = [_aplic("2026-10-08", 3), _aplic("2026-10-09", 30), _aplic("2026-10-01", 15)]
        self.assertEqual(fim_da_carencia(aplicacoes, REF), date(2026, 11, 8))

    def test_aplicacao_depois_da_referencia_nao_conta(self):
        """Venda lançada com data passada não é travada por remédio dado depois."""
        self.assertIsNone(fim_da_carencia([_aplic("2026-10-12", 30)], REF))

    def test_sem_dias_de_carencia_e_ignorada(self):
        self.assertIsNone(fim_da_carencia([_aplic("2026-10-09", 0), _aplic("2026-10-09", None)], REF))

    def test_dado_invalido_e_ignorado_sem_derrubar_o_resto(self):
        aplicacoes = [_aplic("nao-e-data", 10), _aplic(None, 10), {"withdrawal_days": 10},
                      _aplic("2026-10-09", "dez"), _aplic("2026-10-09", 5)]
        self.assertEqual(fim_da_carencia(aplicacoes, REF), date(2026, 10, 14))

    def test_aceita_med_date_como_date(self):
        self.assertEqual(fim_da_carencia([_aplic(date(2026, 10, 9), 5)], REF), date(2026, 10, 14))


if __name__ == "__main__":
    unittest.main()
