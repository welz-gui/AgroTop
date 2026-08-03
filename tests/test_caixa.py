import unittest

from services.caixa import em_aberto, fluxo_de_caixa, resultado_por_competencia


class TestCaixa(unittest.TestCase):
    def test_resultado_por_competencia_soma_receita_e_despesa_e_calcula_resultado(self):
        lancamentos = [
            {
                "tipo": "receita",
                "categoria": "venda",
                "valor": 100.0,
                "competencia": "2026-03-15",
                "vencimento": "2026-04-15",
                "pagamento": "2026-04-10",
            },
            {
                "tipo": "despesa",
                "categoria": "racao",
                "valor": 20.0,
                "competencia": "2026-03-05",
                "vencimento": "2026-03-30",
                "pagamento": None,
            },
        ]

        resultado = resultado_por_competencia(lancamentos, 2026, 3)

        self.assertEqual(resultado["receitas"], 100.0)
        self.assertEqual(resultado["despesas"], 20.0)
        self.assertEqual(resultado["resultado"], 80.0)
        self.assertEqual(resultado["por_categoria"], [
            {"categoria": "racao", "valor": 20.0},
            {"categoria": "venda", "valor": 100.0},
        ])

    def test_fluxo_de_caixa_separa_realizado_e_projetado(self):
        lancamentos = [
            {
                "tipo": "despesa",
                "categoria": "racao",
                "valor": 15.0,
                "competencia": "2026-03-01",
                "vencimento": "2026-03-20",
                "pagamento": "2026-03-10",
            },
            {
                "tipo": "despesa",
                "categoria": "salario",
                "valor": 30.0,
                "competencia": "2026-03-01",
                "vencimento": "2026-03-25",
                "pagamento": None,
            },
        ]

        resultado = fluxo_de_caixa(lancamentos, "2026-03-01", "2026-03-31")

        self.assertEqual(resultado["realizado"], 15.0)
        self.assertEqual(resultado["projetado"], 30.0)
        self.assertEqual(resultado["saldo_projetado"], 45.0)

    def test_em_aberto_ordena_vencidas_primeiro_e_hoje_nao_e_atraso(self):
        lancamentos = [
            {
                "tipo": "despesa",
                "categoria": "racao",
                "valor": 15.0,
                "competencia": "2026-03-01",
                "vencimento": "2026-03-15",
                "pagamento": None,
            },
            {
                "tipo": "despesa",
                "categoria": "salario",
                "valor": 30.0,
                "competencia": "2026-03-01",
                "vencimento": "2026-03-18",
                "pagamento": None,
            },
        ]

        resultado = em_aberto(lancamentos, "2026-03-18")

        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]["categoria"], "racao")
        self.assertEqual(resultado[0]["dias_atraso"], 3)
        self.assertEqual(resultado[1]["dias_atraso"], 0)

    def test_lancamento_sem_pagamento_nao_entra_em_realizado(self):
        lancamentos = [
            {
                "tipo": "despesa",
                "categoria": "salario",
                "valor": 30.0,
                "competencia": "2026-03-01",
                "vencimento": "2026-03-25",
                "pagamento": None,
            },
        ]

        resultado = fluxo_de_caixa(lancamentos, "2026-03-01", "2026-03-31")
        self.assertEqual(resultado["realizado"], 0.0)
        self.assertEqual(resultado["projetado"], 30.0)

    def test_dados_malformados_sao_ignorados(self):
        lancamentos = [
            {
                "tipo": "despesa",
                "categoria": "salario",
                "valor": 30.0,
                "competencia": "2026-03-01",
                "vencimento": "invalid-date",
                "pagamento": None,
            },
        ]

        resultado = resultado_por_competencia(lancamentos, 2026, 3)
        self.assertEqual(resultado["receitas"], 0.0)
        self.assertEqual(resultado["despesas"], 0.0)
        self.assertEqual(resultado["resultado"], 0.0)

    def test_mes_sem_lancamentos_devolve_zeros(self):
        resultado = resultado_por_competencia([], 2026, 3)
        self.assertEqual(resultado["receitas"], 0.0)
        self.assertEqual(resultado["despesas"], 0.0)
        self.assertEqual(resultado["resultado"], 0.0)


if __name__ == "__main__":
    unittest.main()
