import unittest

from services.dieta import custo_por_arroba_produzida, custo_por_cabeca_dia


class TestDieta(unittest.TestCase):
    def test_lista_vazia_devolve_zeros(self):
        resultado = custo_por_cabeca_dia([])
        self.assertEqual(resultado["custo_dia"], 0.0)
        self.assertEqual(resultado["kg_materia_natural"], 0.0)
        self.assertEqual(resultado["kg_materia_seca"], 0.0)
        self.assertEqual(resultado["participacao"], [])

    def test_kg_materia_seca_30_porcento(self):
        ingredientes = [
            {
                "insumo_id": 1,
                "nome": "silagem",
                "quantidade_kg_cabeca_dia": 10.0,
                "custo_por_kg": 1.20,
                "materia_seca_pct": 30.0,
            }
        ]
        resultado = custo_por_cabeca_dia(ingredientes)
        self.assertEqual(resultado["kg_materia_seca"], 3.0)
        self.assertEqual(resultado["custo_dia"], 12.0)
        self.assertEqual(resultado["kg_materia_natural"], 10.0)
        self.assertEqual(resultado["participacao"], [{"nome": "silagem", "pct_custo": 100.0}])

    def test_participacao_soma_cem_porcento_e_ordem(self):
        ingredientes = [
            {
                "insumo_id": 1,
                "nome": "milho",
                "quantidade_kg_cabeca_dia": 5.0,
                "custo_por_kg": 3.0,
                "materia_seca_pct": 88.0,
            },
            {
                "insumo_id": 2,
                "nome": "silagem",
                "quantidade_kg_cabeca_dia": 10.0,
                "custo_por_kg": 1.0,
                "materia_seca_pct": 30.0,
            },
        ]
        resultado = custo_por_cabeca_dia(ingredientes)
        self.assertEqual(resultado["custo_dia"], 25.0)
        self.assertEqual(resultado["kg_materia_seca"], 7.4)
        self.assertEqual(resultado["participacao"][0]["nome"], "milho")
        self.assertEqual(sum(item["pct_custo"] for item in resultado["participacao"]), 100.0)

    def test_custo_por_arroba_produtiva(self):
        custo = custo_por_arroba_produzida(10.0, 1.0, 0.50)
        self.assertEqual(custo, 300.0)

    def test_custo_por_arroba_retorna_none_para_gmd_zero_ou_negativo(self):
        self.assertIsNone(custo_por_arroba_produzida(10.0, 0.0, 0.50))
        self.assertIsNone(custo_por_arroba_produzida(10.0, -0.5, 0.50))

    def test_materia_seca_pct_fora_de_faixa_rejeita(self):
        with self.assertRaises(ValueError):
            custo_por_cabeca_dia([
                {
                    "insumo_id": 1,
                    "nome": "milho",
                    "quantidade_kg_cabeca_dia": 5.0,
                    "custo_por_kg": 3.0,
                    "materia_seca_pct": 120.0,
                }
            ])

    def test_participacao_com_custo_zero(self):
        resultado = custo_por_cabeca_dia([
            {
                "insumo_id": 1,
                "nome": "palha",
                "quantidade_kg_cabeca_dia": 0.0,
                "custo_por_kg": 0.0,
                "materia_seca_pct": 50.0,
            }
        ])
        self.assertEqual(resultado["custo_dia"], 0.0)
        self.assertEqual(resultado["participacao"], [{"nome": "palha", "pct_custo": 0.0}])


if __name__ == "__main__":
    unittest.main()
