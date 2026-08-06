import unittest

from services.rentabilidade import ranking_por_raca
from services.rentabilidade_adaptador import montar_ciclos


class TestMontarCiclos(unittest.TestCase):
    def test_monta_ciclo_com_todos_os_campos(self):
        resultado = montar_ciclos(
            [{"animal_uuid": "a1", "sale_date": "2024-07-01", "total_value": 2000}],
            {
                "a1": {
                    "breed": "Nelore",
                    "entry_weight": 350,
                    "current_weight": 500,
                    "entry_date": "2024-01-01",
                }
            },
            {"a1": 1250.5},
        )

        self.assertEqual(
            resultado,
            [
                {
                    "raca": "Nelore",
                    "peso_entrada": 350.0,
                    "peso_saida": 500.0,
                    "custo_total": 1250.5,
                    "receita": 2000.0,
                    "dias": 182,
                }
            ],
        )

    def test_venda_sem_animal_e_ignorada(self):
        resultado = montar_ciclos(
            [{"animal_uuid": "ausente", "sale_date": "2024-07-01", "total_value": 2000}],
            {},
            {},
        )

        self.assertEqual(resultado, [])

    def test_custo_ausente_vira_zero_e_nao_descarta_venda(self):
        resultado = montar_ciclos(
            [{"animal_uuid": "a1", "sale_date": "2024-02-01", "total_value": 900}],
            {
                "a1": {
                    "breed": "Angus",
                    "entry_weight": 300,
                    "current_weight": 400,
                    "entry_date": "2024-01-01",
                }
            },
            {},
        )

        self.assertEqual(resultado[0]["custo_total"], 0.0)
        self.assertEqual(resultado[0]["receita"], 900.0)

    def test_duas_vendas_do_mesmo_animal_geram_dois_ciclos(self):
        vendas = [
            {"animal_uuid": "a1", "sale_date": "2024-02-01", "total_value": 1000},
            {"animal_uuid": "a1", "sale_date": "2024-03-01", "total_value": 1200},
        ]
        animais = {
            "a1": {
                "breed": "Brangus",
                "entry_weight": 300,
                "current_weight": 400,
                "entry_date": "2024-01-01",
            }
        }

        resultado = montar_ciclos(vendas, animais, {"a1": 500})

        self.assertEqual(len(resultado), 2)
        self.assertEqual([ciclo["receita"] for ciclo in resultado], [1000.0, 1200.0])
        self.assertEqual([ciclo["dias"] for ciclo in resultado], [31, 60])

    def test_dias_nunca_ficam_negativos(self):
        resultado = montar_ciclos(
            [{"animal_uuid": "a1", "sale_date": "2024-01-01", "total_value": 1000}],
            {
                "a1": {
                    "breed": "Guzera",
                    "entry_weight": 400,
                    "current_weight": 420,
                    "entry_date": "2024-02-01",
                }
            },
            {"a1": 300},
        )

        self.assertEqual(resultado[0]["dias"], 0)

    def test_ranking_preserva_margem_negativa(self):
        ciclos = montar_ciclos(
            [
                {"animal_uuid": "a1", "sale_date": "2024-07-01", "total_value": 2000},
                {"animal_uuid": "a2", "sale_date": "2024-07-01", "total_value": 1500},
            ],
            {
                "a1": {
                    "breed": "Nelore",
                    "entry_weight": 350,
                    "current_weight": 500,
                    "entry_date": "2024-01-01",
                },
                "a2": {
                    "breed": "Angus",
                    "entry_weight": 350,
                    "current_weight": 500,
                    "entry_date": "2024-01-01",
                },
            },
            {"a1": 1000, "a2": 2500},
        )

        ranking = ranking_por_raca(ciclos)
        por_raca = {item["raca"]: item for item in ranking}
        self.assertLess(por_raca["Angus"]["margem"], 0)
        self.assertAlmostEqual(por_raca["Angus"]["margem"], -0.6667)


if __name__ == "__main__":
    unittest.main()
