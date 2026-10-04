"""Testes unitários para services.rateio_adaptador (Spec 0041)."""

import unittest
from datetime import date
from services.rateio_adaptador import com_dias_no_lote, _parse_date
from services.rateio import ratear


class TestRateioAdaptador(unittest.TestCase):

    def test_parse_date_with_valid_date_object(self):
        """Testa se a função retorna a data correta se uma data válida for passada."""
        dt = date(2023, 10, 15)
        self.assertEqual(_parse_date(dt), dt)

    def test_parse_date_with_valid_iso_string(self):
        """Testa se a função converte corretamente uma string ISO válida para data."""
        self.assertEqual(_parse_date("2023-10-15"), date(2023, 10, 15))

    def test_parse_date_with_time_component(self):
        """Testa se a função trunca a string com componente de tempo corretamente e converte."""
        self.assertEqual(_parse_date("2023-10-15T10:30:00"), date(2023, 10, 15))

    def test_parse_date_with_invalid_format_string(self):
        """Testa se a função retorna None para uma string com formato inválido."""
        self.assertIsNone(_parse_date("15/10/2023"))

    def test_parse_date_with_structurally_valid_but_invalid_calendar_date(self):
        """Testa se a função retorna None para string bem formatada, mas dia inválido (ex: ano bissexto)."""
        self.assertIsNone(_parse_date("2021-02-29"))

    def test_parse_date_with_short_string(self):
        """Testa se a função retorna None para uma string com tamanho menor que 10 caracteres."""
        self.assertIsNone(_parse_date("2023-1"))

    def test_parse_date_with_none_or_integer(self):
        """Testa se a função retorna None para valores como None ou inteiro."""
        self.assertIsNone(_parse_date(None))
        self.assertIsNone(_parse_date(123456))

    def test_parse_date_with_type_error(self):
        """Testa se a função lida adequadamente quando fromisoformat levanta TypeError."""
        # By passing a custom subclass of str that raises TypeError in a mock way,
        # we can test the TypeError catch without mocking `date` itself and breaking isinstance.
        class MyBadString(str):
            def __getitem__(self, key):
                raise TypeError("Mock TypeError")

        bad_str = MyBadString("2023-10-15")
        # Ensure it acts as a string with length > 10 for the if statement
        self.assertIsNone(_parse_date(bad_str))

    def test_criterio_1_entrada_10_dias_antes_da_referencia(self):
        """Critério 1: Animal com entrada_no_lote 10 dias antes da referencia recebe dias_no_lote=10."""
        animais = [
            {"id": "a1", "peso": 450.0, "entrada_no_lote": "2026-08-01"}
        ]
        res = com_dias_no_lote(animais, referencia="2026-08-11")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["dias_no_lote"], 10)

    def test_criterio_2_entrada_none_recebe_zero(self):
        """Critério 2: Animal com entrada_no_lote=None recebe dias_no_lote=0."""
        animais = [
            {"id": "a2", "peso": 400.0, "entrada_no_lote": None}
        ]
        res = com_dias_no_lote(animais, referencia="2026-08-11")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["dias_no_lote"], 0)

    def test_criterio_3_entrada_futura_recebe_zero_nao_negativo(self):
        """Critério 3: Animal com entrada_no_lote posterior à referência recebe dias_no_lote=0, não negativo."""
        animais = [
            {"id": "a3", "peso": 420.0, "entrada_no_lote": "2026-08-20"}
        ]
        res = com_dias_no_lote(animais, referencia="2026-08-11")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["dias_no_lote"], 0)

    def test_criterio_4_preserva_demais_campos_intactos(self):
        """Critério 4: Campos originais (id, peso, raca, etc.) permanecem intactos na saída."""
        animais = [
            {"id": "a4", "peso": 500.0, "entrada_no_lote": "2026-08-01", "raca": "Nelore", "lote_id": 99}
        ]
        res = com_dias_no_lote(animais, referencia="2026-08-11")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], "a4")
        self.assertEqual(res[0]["peso"], 500.0)
        self.assertEqual(res[0]["raca"], "Nelore")
        self.assertEqual(res[0]["lote_id"], 99)
        self.assertEqual(res[0]["dias_no_lote"], 10)

    def test_criterio_5_integra_com_rateio_ratear_peso_dia(self):
        """Critério 5: Resultado passado para rateio.ratear(valor, resultado, 'peso_dia') fecha o valor exato."""
        animais = [
            {"id": "a1", "peso": 400.0, "entrada_no_lote": "2026-08-01"},  # 10 dias
            {"id": "a2", "peso": 500.0, "entrada_no_lote": "2026-08-06"},  # 5 dias
            {"id": "a3", "peso": 300.0, "entrada_no_lote": None},          # 0 dias
        ]
        animais_com_dias = com_dias_no_lote(animais, referencia="2026-08-11")
        
        valor_total = 1000.00
        rateado = ratear(valor_total, animais_com_dias, "peso_dia")
        self.assertEqual(len(rateado), 3)

        soma = sum(item["valor"] for item in rateado)
        self.assertAlmostEqual(soma, valor_total, places=2)


if __name__ == "__main__":
    unittest.main()
