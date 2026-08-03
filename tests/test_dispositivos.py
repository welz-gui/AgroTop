import unittest
from services.dispositivos import (
    expandir_faixa,
    validar_aplicacao,
    situacao_do_estoque,
)


class TestDispositivosEstoque(unittest.TestCase):
    def test_expandir_faixa_basica(self):
        res = expandir_faixa("BR0001", "BR0010")
        self.assertEqual(len(res), 10)
        self.assertEqual(res[0], "BR0001")
        self.assertEqual(res[-1], "BR0010")
        self.assertEqual(
            res,
            [
                "BR0001",
                "BR0002",
                "BR0003",
                "BR0004",
                "BR0005",
                "BR0006",
                "BR0007",
                "BR0008",
                "BR0009",
                "BR0010",
            ],
        )

    def test_expandir_faixa_prefixos_diferentes_dispara_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            expandir_faixa("BR0001", "MT0010")
        self.assertIn("Prefixos divergentes", str(ctx.exception))

    def test_expandir_faixa_invertida_dispara_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            expandir_faixa("BR0010", "BR0001")
        self.assertIn("menor que o início", str(ctx.exception))

    def test_validar_aplicacao_codigos(self):
        faixas = [
            {"inicio": "BR0001", "fim": "BR0100", "status": "disponivel"},
            {"inicio": "BR0900", "fim": "BR0999", "status": "cancelada"},
        ]
        aplicados = {
            "BR0001": {"animal_uuid": "uuid-123", "status": "ativo"},
            "BR0002": {"animal_uuid": "uuid-456", "status": "removido"},
        }

        # 1. fora_das_faixas
        res_fora = validar_aplicacao("BR0500", faixas, aplicados)
        self.assertFalse(res_fora["pode"])
        self.assertEqual(res_fora["codigo"], "fora_das_faixas")

        # 2. faixa_cancelada
        res_canc = validar_aplicacao("BR0950", faixas, aplicados)
        self.assertFalse(res_canc["pode"])
        self.assertEqual(res_canc["codigo"], "faixa_cancelada")

        # 3. ja_aplicado_ativo
        res_ativo = validar_aplicacao("BR0001", faixas, aplicados)
        self.assertFalse(res_ativo["pode"])
        self.assertEqual(res_ativo["codigo"], "ja_aplicado_ativo")
        self.assertIn("uuid-123", res_ativo["motivo"])

        # 4. reaproveitavel (status == "removido")
        res_reap = validar_aplicacao("BR0002", faixas, aplicados)
        self.assertTrue(res_reap["pode"])
        self.assertEqual(res_reap["codigo"], "reaproveitavel")

        # 5. disponivel
        res_disp = validar_aplicacao("BR0003", faixas, aplicados)
        self.assertTrue(res_disp["pode"])
        self.assertEqual(res_disp["codigo"], "disponivel")

    def test_situacao_do_estoque_faixa_grande_otimizada(self):
        # 100 mil números na faixa
        faixas = [
            {"inicio": "BR000001", "fim": "BR100000", "status": "disponivel"}
        ]
        aplicados = {
            "BR000001": {"animal_uuid": "uuid-1", "status": "ativo"},
            "BR000002": {"animal_uuid": "uuid-2", "status": "ativo"},
            "BR000003": {"animal_uuid": "uuid-3", "status": "removido"},
        }

        sit = situacao_do_estoque(faixas, aplicados)
        self.assertEqual(sit["total"], 100000)
        self.assertEqual(sit["aplicados"], 2)
        self.assertEqual(sit["disponiveis"], 99998)
        self.assertEqual(sit["percentual_usado"], 0.0)

        # Próximos 10 disponíveis (pula BR000001 e BR000002 pois são ativos; BR000003 é removido logo é disponível!)
        self.assertEqual(len(sit["proximos_disponiveis"]), 10)
        self.assertEqual(sit["proximos_disponiveis"][0], "BR000003")
        self.assertEqual(sit["proximos_disponiveis"][1], "BR000004")
        self.assertEqual(sit["proximos_disponiveis"][9], "BR000012")

    def test_proximos_disponiveis_ordem_numerica(self):
        faixas = [{"inicio": "BR0008", "fim": "BR0012", "status": "disponivel"}]
        sit = situacao_do_estoque(faixas, {})
        # Ordem numérica: BR0008, BR0009, BR0010, BR0011, BR0012
        # Em ordem alfabética pura o BR0010 viria antes do BR0009. Na ordem numérica o BR0009 vem antes do BR0010.
        self.assertEqual(
            sit["proximos_disponiveis"],
            ["BR0008", "BR0009", "BR0010", "BR0011", "BR0012"],
        )


if __name__ == "__main__":
    unittest.main()
