import unittest

from services.compras import gerar_parcelas, total_compra


class TestTotalCompra(unittest.TestCase):
    def test_soma_itens(self):
        itens = [
            {"quantidade": 10.0, "custo_unitario": 5.0},
            {"quantidade": 3.0, "custo_unitario": 12.5},
        ]
        self.assertEqual(total_compra(itens), 87.5)

    def test_lista_vazia_e_zero(self):
        self.assertEqual(total_compra([]), 0.0)

    def test_ignora_chaves_extras(self):
        itens = [{"insumo_id": 7, "quantidade": 2.0, "custo_unitario": 3.0, "nome": "Ração"}]
        self.assertEqual(total_compra(itens), 6.0)

    def test_arredonda_duas_casas(self):
        itens = [{"quantidade": 3.0, "custo_unitario": 3.333}]
        self.assertEqual(total_compra(itens), 10.0)


class TestGerarParcelas(unittest.TestCase):
    def test_parcela_unica_igual_ao_total(self):
        parcelas = gerar_parcelas(300.0, 1, "2026-09-10")
        self.assertEqual(len(parcelas), 1)
        self.assertEqual(parcelas[0]["valor"], 300.0)
        self.assertEqual(parcelas[0]["vencimento"], "2026-09-10")
        self.assertEqual(parcelas[0]["numero"], 1)
        self.assertEqual(parcelas[0]["total"], 1)

    def test_resto_da_divisao_vai_para_a_ultima_parcela(self):
        """R$ 100 em 3x: 33,33 + 33,33 + 33,34 — soma exata, sem sobrar centavo."""
        parcelas = gerar_parcelas(100.0, 3, "2026-01-05")
        valores = [p["valor"] for p in parcelas]
        self.assertEqual(valores, [33.33, 33.33, 33.34])
        self.assertEqual(round(sum(valores), 2), 100.0)

    def test_vencimentos_avancam_um_mes_por_parcela(self):
        parcelas = gerar_parcelas(300.0, 3, "2026-01-15")
        vencimentos = [p["vencimento"] for p in parcelas]
        self.assertEqual(vencimentos, ["2026-01-15", "2026-02-15", "2026-03-15"])

    def test_vencimento_atravessa_o_ano(self):
        parcelas = gerar_parcelas(200.0, 2, "2026-12-20")
        vencimentos = [p["vencimento"] for p in parcelas]
        self.assertEqual(vencimentos, ["2026-12-20", "2027-01-20"])

    def test_dia_31_cai_para_o_ultimo_dia_do_mes_curto(self):
        """Comprar dia 31/01 não pode gerar '2026-02-31' (não existe)."""
        parcelas = gerar_parcelas(200.0, 2, "2026-01-31")
        vencimentos = [p["vencimento"] for p in parcelas]
        self.assertEqual(vencimentos, ["2026-01-31", "2026-02-28"])

    def test_dia_31_em_ano_bissexto(self):
        parcelas = gerar_parcelas(200.0, 2, "2028-01-31")
        vencimentos = [p["vencimento"] for p in parcelas]
        self.assertEqual(vencimentos, ["2028-01-31", "2028-02-29"])

    def test_num_parcelas_invalido_leva_a_erro(self):
        with self.assertRaises(ValueError):
            gerar_parcelas(100.0, 0, "2026-01-01")


if __name__ == "__main__":
    unittest.main()
