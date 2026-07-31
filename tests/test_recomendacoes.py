import unittest
from services.recomendacoes import avaliar


class TestMotorRecomendacoes(unittest.TestCase):
    def setUp(self):
        self.hoje = "2026-05-10"

    def test_contexto_vazio_e_none(self):
        self.assertEqual(avaliar(None), [])
        self.assertEqual(avaliar({}), [])
        self.assertEqual(avaliar({"hoje": "2026-05-10"}), [])

    def test_estoque_insuficiente_dispara_e_nao_dispara(self):
        ctx_dispara = {
            "insumos": [
                {
                    "id": 1,
                    "nome": "Ração Milho",
                    "saldo": 100.0,
                    "consumo_diario": 10.0,
                }
            ]
        }
        recs = avaliar(ctx_dispara)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["regra"], "estoque_insuficiente")
        self.assertEqual(recs[0]["severidade"], "alta")
        self.assertIn("Ração Milho", recs[0]["titulo"])
        self.assertIn("motivo", recs[0])
        self.assertIn("dados", recs[0])
        self.assertEqual(recs[0]["dados"]["dias_restantes"], 10.0)

        ctx_ok = {
            "insumos": [
                {
                    "id": 1,
                    "nome": "Ração Milho",
                    "saldo": 200.0,
                    "consumo_diario": 10.0,
                }
            ]
        }
        self.assertEqual(avaliar(ctx_ok), [])

    def test_piquete_acima_da_capacidade_dispara_e_nao_dispara(self):
        ctx_dispara = {
            "lotes": [
                {
                    "id": "L1",
                    "nome": "P3",
                    "ua_atual": 32.5,
                    "capacidade_ua": 28.0,
                }
            ]
        }
        recs = avaliar(ctx_dispara)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["regra"], "piquete_acima_da_capacidade")
        self.assertEqual(recs[0]["severidade"], "alta")
        self.assertIn("P3", recs[0]["titulo"])
        self.assertIn("motivo", recs[0])
        self.assertEqual(recs[0]["dados"]["excesso_ua"], 4.5)

        ctx_ok = {
            "lotes": [
                {
                    "id": "L1",
                    "nome": "P3",
                    "ua_atual": 25.0,
                    "capacidade_ua": 28.0,
                }
            ]
        }
        self.assertEqual(avaliar(ctx_ok), [])

    def test_carencia_impede_abate_dispara(self):
        ctx = {
            "hoje": self.hoje,
            "animais": [
                {
                    "id": "BR001",
                    "peso": 520.0,
                    "peso_alvo": 500.0,
                    "carencia_ate": "2026-06-01",
                }
            ],
        }
        recs = avaliar(ctx)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["regra"], "carencia_impede_abate")
        self.assertEqual(recs[0]["severidade"], "alta")
        self.assertIn("BR001", recs[0]["titulo"])
        self.assertIn("motivo", recs[0])
        self.assertEqual(recs[0]["dados"]["carencia_ate"], "2026-06-01")

    def test_pronto_para_venda_dispara(self):
        ctx = {
            "hoje": self.hoje,
            "animais": [
                {
                    "id": "BR002",
                    "peso": 510.0,
                    "peso_alvo": 500.0,
                    "carencia_ate": "2026-05-01",
                }
            ],
        }
        recs = avaliar(ctx)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["regra"], "pronto_para_venda")
        self.assertEqual(recs[0]["severidade"], "media")
        self.assertIn("BR002", recs[0]["titulo"])
        self.assertIn("motivo", recs[0])

    def test_gmd_abaixo_da_meta_dispara_e_nao_dispara(self):
        ctx_dispara = {
            "animais": [{"id": "BR003", "gmd": 0.35, "meta_gmd": 0.5}]
        }
        recs = avaliar(ctx_dispara)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["regra"], "gmd_abaixo_da_meta")
        self.assertEqual(recs[0]["severidade"], "media")
        self.assertEqual(recs[0]["dados"]["diferenca"], 0.15)

        ctx_ok = {"animais": [{"id": "BR003", "gmd": 0.6, "meta_gmd": 0.5}]}
        self.assertEqual(avaliar(ctx_ok), [])

    def test_margem_em_risco_dispara_e_nao_dispara(self):
        ctx_dispara = {
            "custo_por_arroba": 320.0,
            "preco_arroba": 300.0,
        }
        recs = avaliar(ctx_dispara)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["regra"], "margem_em_risco")
        self.assertEqual(recs[0]["severidade"], "alta")
        self.assertEqual(recs[0]["dados"]["prejuizo_por_arroba"], 20.0)

        ctx_ok = {
            "custo_por_arroba": 280.0,
            "preco_arroba": 300.0,
        }
        self.assertEqual(avaliar(ctx_ok), [])

    def test_chaves_faltando_no_contexto_pula_regras_dependentes(self):
        ctx = {
            "insumos": [
                {
                    "id": 1,
                    "nome": "Sal Mineral",
                    "saldo": 5.0,
                    "consumo_diario": 1.0,
                }
            ]
        }
        recs = avaliar(ctx)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["regra"], "estoque_insuficiente")

    def test_varias_regras_disparando_juntas_e_campos_obrigatorios(self):
        ctx = {
            "hoje": self.hoje,
            "insumos": [
                {
                    "id": 1,
                    "nome": "Silagem",
                    "saldo": 50.0,
                    "consumo_diario": 10.0,
                }
            ],
            "lotes": [
                {
                    "id": "L1",
                    "nome": "Lote 1",
                    "ua_atual": 40.0,
                    "capacidade_ua": 30.0,
                }
            ],
            "animais": [
                {
                    "id": "A1",
                    "peso": 550.0,
                    "peso_alvo": 500.0,
                    "carencia_ate": "2026-06-15",
                },
                {"id": "A2", "gmd": 0.2, "meta_gmd": 0.5},
            ],
            "custo_por_arroba": 350.0,
            "preco_arroba": 310.0,
        }
        recs = avaliar(ctx)
        self.assertGreaterEqual(len(recs), 4)

        for r in recs:
            self.assertIn("regra", r)
            self.assertIn("severidade", r)
            self.assertIn("titulo", r)
            self.assertIn("motivo", r)
            self.assertIn("dados", r)
            self.assertIn("acao", r)
            self.assertTrue(len(r["motivo"]) > 0)
            self.assertIsInstance(r["dados"], dict)
            self.assertTrue(len(r["dados"]) > 0)


if __name__ == "__main__":
    unittest.main()
