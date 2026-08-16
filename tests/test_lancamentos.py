"""Testes unitários para services.lancamentos (Spec 0034)."""

import unittest
from services.lancamentos import normalizar
from services.caixa import resultado_por_competencia


class TestLancamentos(unittest.TestCase):

    def test_criterio_1_venda_devolve_receita_com_tres_datas_iguais(self):
        """Critério 1: Venda de R$ 3000 gera receita com as três datas iguais."""
        vendas = [{"sale_date": "2026-08-01", "total_value": 3000.0}]
        res = normalizar(vendas=vendas)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["tipo"], "receita")
        self.assertEqual(res[0]["categoria"], "venda")
        self.assertEqual(res[0]["valor"], 3000.0)
        self.assertEqual(res[0]["competencia"], "2026-08-01")
        self.assertEqual(res[0]["vencimento"], "2026-08-01")
        self.assertEqual(res[0]["pagamento"], "2026-08-01")

    def test_criterio_2_custo_fixo_negativo_preserva_sinal(self):
        """Critério 2: Custo fixo negativo (estorno de R$ -200) mantém o sinal."""
        custos_fixos = [
            {"cost_date": "2026-08-02", "amount": -200.0, "category": "Energia"}
        ]
        res = normalizar(custos_fixos=custos_fixos)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["tipo"], "despesa")
        self.assertEqual(res[0]["valor"], -200.0)
        self.assertEqual(res[0]["categoria"], "Energia")

    def test_criterio_3_transacao_de_consumo_nao_gera_lancamento(self):
        """Critério 3: Transação de insumo do tipo 'consumo' não gera lançamento."""
        compras = [
            {"transaction_date": "2026-08-03", "quantity": 10, "type": "consumo", "insumo": {"cost_per_unit": 5.0}},
            {"transaction_date": "2026-08-03", "quantity": 10, "type": "ajuste", "insumo": {"cost_per_unit": 5.0}},
        ]
        res = normalizar(compras_insumo=compras)
        self.assertEqual(len(res), 0)

    def test_criterio_4_compra_de_insumo_sem_insumo_embutido_ou_sem_preco(self):
        """Critério 4: Compra de insumo sem `insumo` embutido ou sem `cost_per_unit` não estoura."""
        compras = [
            {"transaction_date": "2026-08-04", "quantity": 10, "type": "compra"},
            {"transaction_date": "2026-08-04", "quantity": 10, "type": "compra", "insumo": None},
            {"transaction_date": "2026-08-04", "quantity": 10, "type": "compra", "insumo": {"name": "Ração"}},
        ]
        res = normalizar(compras_insumo=compras)
        self.assertEqual(len(res), 3)
        for item in res:
            self.assertEqual(item["valor"], 0.0)

    def test_criterio_5_listas_vazias_devolvem_lista_vazia(self):
        """Critério 5: As quatro listas vazias devolvem lista vazia."""
        res = normalizar()
        self.assertEqual(res, [])
        res2 = normalizar(vendas=[], custos_fixos=[], custos_animal=[], compras_insumo=[])
        self.assertEqual(res2, [])

    def test_criterio_6_integra_com_caixa_resultado_por_competencia(self):
        """Critério 6: O resultado de normalizar() passado para caixa.resultado_por_competencia() bate o teste do centavo."""
        vendas = [{"sale_date": "2026-08-10", "total_value": 5000.0}]
        custos_fixos = [{"cost_date": "2026-08-12", "amount": 1200.50, "category": "Aluguel"}]
        custos_animal = [{"cost_date": "2026-08-15", "amount": 300.25, "cost_type": "Vacina"}]
        compras = [
            {
                "transaction_date": "2026-08-20",
                "quantity": 100,
                "type": "compra",
                "insumo": {"name": "Milho", "cost_per_unit": 2.50},
            }
        ]

        lancamentos = normalizar(
            vendas=vendas,
            custos_fixos=custos_fixos,
            custos_animal=custos_animal,
            compras_insumo=compras,
        )

        res_caixa = resultado_por_competencia(lancamentos, 2026, 8)
        self.assertEqual(res_caixa["receitas"], 5000.0)
        # despesas = 1200.50 + 300.25 + (100 * 2.50 = 250.0) = 1750.75
        self.assertEqual(res_caixa["despesas"], 1750.75)
        self.assertEqual(res_caixa["resultado"], 3249.25)
        self.assertAlmostEqual(
            res_caixa["receitas"] - res_caixa["despesas"],
            res_caixa["resultado"],
            places=2,
        )

    def test_categoria_ausente_vira_string_vazia(self):
        """Testa que categoria ausente vira '', nunca None."""
        custos_fixos = [{"cost_date": "2026-08-01", "amount": 50.0, "category": None}]
        res = normalizar(custos_fixos=custos_fixos)
        self.assertEqual(res[0]["categoria"], "")

    def test_conta_a_pagar_vira_despesa_sem_competencia(self):
        """Cronograma de caixa, não fato novo: competencia sai None de
        propósito, para `resultado_por_competencia` nunca contar de novo o
        que já foi reconhecido no lançamento de origem (a compra)."""
        contas_pagar = [{
            "valor": 500.0, "descricao": "Compra NF-1 — Fornecedor X",
            "vencimento": "2026-09-10", "data_pagamento": None,
        }]
        res = normalizar(contas_pagar=contas_pagar)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["tipo"], "despesa")
        self.assertEqual(res[0]["valor"], 500.0)
        self.assertEqual(res[0]["categoria"], "Compra NF-1 — Fornecedor X")
        self.assertIsNone(res[0]["competencia"])
        self.assertEqual(res[0]["vencimento"], "2026-09-10")
        self.assertIsNone(res[0]["pagamento"])

    def test_conta_a_pagar_paga_traz_a_data_de_pagamento(self):
        contas_pagar = [{
            "valor": 500.0, "descricao": "x", "vencimento": "2026-09-10",
            "data_pagamento": "2026-09-08",
        }]
        res = normalizar(contas_pagar=contas_pagar)
        self.assertEqual(res[0]["pagamento"], "2026-09-08")

    def test_conta_a_receber_vira_receita_sem_competencia(self):
        contas_receber = [{
            "valor": 3000.0, "descricao": "Venda — Frigorífico Y",
            "vencimento": "2026-10-01", "data_recebimento": None,
        }]
        res = normalizar(contas_receber=contas_receber)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["tipo"], "receita")
        self.assertEqual(res[0]["valor"], 3000.0)
        self.assertIsNone(res[0]["competencia"])
        self.assertEqual(res[0]["vencimento"], "2026-10-01")
        self.assertIsNone(res[0]["pagamento"])

    def test_contas_a_pagar_e_receber_nunca_contam_em_resultado_por_competencia(self):
        """`competencia=None` faz `_competencia_mes` sempre devolver falso —
        travando que estas linhas não inflam a Competência/DRE."""
        lancamentos = normalizar(
            contas_pagar=[{"valor": 500.0, "vencimento": "2026-09-10"}],
            contas_receber=[{"valor": 3000.0, "vencimento": "2026-10-01"}])
        resultado = resultado_por_competencia(lancamentos, 2026, 9)
        self.assertEqual(resultado["receitas"], 0.0)
        self.assertEqual(resultado["despesas"], 0.0)


if __name__ == "__main__":
    unittest.main()
