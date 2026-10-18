"""Produto aplicado no tratamento: princípio ativo, lote e validade (regra pura)."""

import unittest

from services.tratamento import (
    LIMITE_LOTE,
    LIMITE_PRINCIPIO_ATIVO,
    TratamentoInvalido,
    normalizar_produto,
)


class TestNormalizarProduto(unittest.TestCase):
    def test_tudo_vazio_e_valido_e_devolve_vazios(self):
        self.assertEqual(
            normalizar_produto(None, None, None, "2026-10-10"),
            {"principio_ativo": "", "lote_produto": "", "validade_produto": ""},
        )

    def test_normaliza_espacos_nas_pontas_e_no_meio(self):
        r = normalizar_produto("  Ivermectina   1% ", "  L2410A ", "2027-01-31", "2026-10-10")
        self.assertEqual(r["principio_ativo"], "Ivermectina 1%")
        self.assertEqual(r["lote_produto"], "L2410A")
        self.assertEqual(r["validade_produto"], "2027-01-31")

    def test_validade_anterior_a_aplicacao_e_recusada_e_a_mensagem_diz_as_datas(self):
        with self.assertRaises(TratamentoInvalido) as ctx:
            normalizar_produto("", "L1", "2026-10-09", "2026-10-10")
        self.assertIn("2026-10-09", str(ctx.exception))
        self.assertIn("2026-10-10", str(ctx.exception))
        self.assertIsInstance(ctx.exception, ValueError)

    def test_validade_no_proprio_dia_da_aplicacao_ainda_vale(self):
        r = normalizar_produto("", "", "2026-10-10", "2026-10-10")
        self.assertEqual(r["validade_produto"], "2026-10-10")

    def test_validade_com_formato_invalido_e_recusada(self):
        for ruim in ("31/12/2026", "2026-13-01", "amanha", "20261231"):
            with self.subTest(validade=ruim):
                with self.assertRaises(TratamentoInvalido):
                    normalizar_produto("", "", ruim, "2026-10-10")

    def test_validade_nao_e_conferida_quando_a_data_da_aplicacao_e_ilegivel(self):
        r = normalizar_produto("", "", "2020-01-01", "data-ruim")
        self.assertEqual(r["validade_produto"], "2020-01-01")

    def test_textos_acima_do_limite_sao_recusados(self):
        with self.assertRaises(TratamentoInvalido):
            normalizar_produto("x" * (LIMITE_PRINCIPIO_ATIVO + 1), "", "", "2026-10-10")
        with self.assertRaises(TratamentoInvalido):
            normalizar_produto("", "y" * (LIMITE_LOTE + 1), "", "2026-10-10")
        normalizar_produto("x" * LIMITE_PRINCIPIO_ATIVO, "y" * LIMITE_LOTE, "", "2026-10-10")


if __name__ == "__main__":
    unittest.main()
