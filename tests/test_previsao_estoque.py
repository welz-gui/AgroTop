import unittest
from services.previsao_estoque import prever


class TestPrevisaoEstoque(unittest.TestCase):
    def setUp(self):
        self.hoje = "2026-08-03"

    def test_calculo_basico_dias_restantes(self):
        insumos = [
            {
                "id": 1,
                "nome": "Sal Mineral",
                "saldo": 100.0,
                "consumo_diario": 10.0,
                "estoque_minimo": 10.0,
                "prazo_reposicao_dias": 0,
            }
        ]
        res = prever(insumos, self.hoje)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], 1)
        self.assertEqual(res[0]["dias_restantes"], 10.0)
        self.assertEqual(res[0]["data_ruptura"], "2026-08-13")
        self.assertEqual(res[0]["comprar_ate"], "2026-08-13")

    def test_prazo_reposicao_calcula_comprar_ate_corretamente(self):
        insumos = [
            {
                "id": 2,
                "nome": "Ração Confinamento",
                "saldo": 100.0,
                "consumo_diario": 10.0,
                "estoque_minimo": 10.0,
                "prazo_reposicao_dias": 7,
            }
        ]
        res = prever(insumos, self.hoje)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["dias_restantes"], 10.0)
        self.assertEqual(res[0]["data_ruptura"], "2026-08-13")
        # 2026-08-13 menos 7 dias = 2026-08-06
        self.assertEqual(res[0]["comprar_ate"], "2026-08-06")

    def test_consumo_zero_devolve_sem_dados(self):
        insumos = [
            {
                "id": 3,
                "nome": "Suplemento Z",
                "saldo": 50.0,
                "consumo_diario": 0.0,
                "estoque_minimo": 0.0,
                "prazo_reposicao_dias": 5,
            }
        ]
        res = prever(insumos, self.hoje)
        self.assertEqual(len(res), 1)
        self.assertIsNone(res[0]["dias_restantes"])
        self.assertIsNone(res[0]["data_ruptura"])
        self.assertIsNone(res[0]["comprar_ate"])
        self.assertEqual(res[0]["urgencia"], "sem_dados")

    def test_divisao_por_zero_e_valores_invalidos_nao_estouram(self):
        insumos = [
            {
                "id": 4,
                "nome": "Insumo Inválido",
                "saldo": "cem",
                "consumo_diario": 0,
            },
            {"id": 5, "nome": "Insumo Negativo", "saldo": -10, "consumo_diario": -5},
        ]
        res = prever(insumos, self.hoje)
        self.assertEqual(len(res), 2)
        for item in res:
            self.assertIsNone(item["dias_restantes"])

    def test_urgencia_critica_quando_comprar_ate_ja_passou_ou_saldo_abaixo_do_minimo(self):
        insumos = [
            {
                "id": 10,
                "nome": "Ureia",
                "saldo": 30.0,  # Abaixo do mínimo de 50
                "consumo_diario": 5.0,
                "estoque_minimo": 50.0,
                "prazo_reposicao_dias": 2,
            },
            {
                "id": 11,
                "nome": "Milho Moído",
                "saldo": 40.0,  # 4 dias restantes (ruptura em 2026-08-07)
                "consumo_diario": 10.0,
                "prazo_reposicao_dias": 10,  # comprar_ate = 2026-07-28 (já passou!)
            },
        ]
        res = prever(insumos, self.hoje)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["urgencia"], "critica")
        self.assertEqual(res[1]["urgencia"], "critica")

    def test_urgencia_atencao_quando_comprar_ate_em_ate_15_dias(self):
        insumos = [
            {
                "id": 20,
                "nome": "Núcleo Mineral",
                "saldo": 200.0,  # 20 dias restantes (ruptura 2026-08-23)
                "consumo_diario": 10.0,
                "prazo_reposicao_dias": 10,  # comprar_ate = 2026-08-13 (em 10 dias)
            }
        ]
        res = prever(insumos, self.hoje)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["urgencia"], "atencao")

    def test_urgencia_ok_quando_prazo_folgado(self):
        insumos = [
            {
                "id": 30,
                "nome": "Farinha de Osso",
                "saldo": 500.0,  # 50 dias restantes (ruptura 2026-09-22)
                "consumo_diario": 10.0,
                "prazo_reposicao_dias": 5,  # comprar_ate = 2026-09-17 (em 45 dias)
            }
        ]
        res = prever(insumos, self.hoje)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["urgencia"], "ok")

    def test_ordenacao_critica_atencao_sem_dados_ok(self):
        insumos = [
            {
                "id": 1,
                "nome": "Item OK",
                "saldo": 500.0,
                "consumo_diario": 10.0,
                "prazo_reposicao_dias": 5,
            },
            {
                "id": 2,
                "nome": "Item Crítico",
                "saldo": 10.0,
                "consumo_diario": 10.0,
                "prazo_reposicao_dias": 5,
            },
            {
                "id": 3,
                "nome": "Item Sem Dados",
                "saldo": 100.0,
                "consumo_diario": 0.0,
                "prazo_reposicao_dias": 5,
            },
            {
                "id": 4,
                "nome": "Item Atenção",
                "saldo": 180.0,
                "consumo_diario": 10.0,
                "prazo_reposicao_dias": 5,
            },
        ]
        res = prever(insumos, self.hoje)
        self.assertEqual(len(res), 4)
        urgencias = [r["urgencia"] for r in res]
        self.assertEqual(urgencias, ["critica", "atencao", "sem_dados", "ok"])

    def test_entrada_vazia_e_invalida(self):
        self.assertEqual(prever([], self.hoje), [])
        self.assertEqual(prever(None, self.hoje), [])


if __name__ == "__main__":
    unittest.main()
