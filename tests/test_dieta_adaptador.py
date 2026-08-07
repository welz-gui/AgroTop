"""Testes unitários para services.dieta_adaptador (Spec 0037)."""

import unittest
from services.dieta_adaptador import ingredientes_por_cabeca
from services.dieta import custo_por_cabeca_dia


class TestDietaAdaptador(unittest.TestCase):

    def test_criterio_1_plano_ativo_devolve_quantidade_por_cabeca_correta(self):
        """Critério 1: Plano ativo de 40 kg/dia de ração para 20 cabeças resulta em 2.0 kg/cabeça/dia."""
        planos = [
            {
                "insumo_id": 1,
                "quantity": 40.0,
                "unit": "kg",
                "frequency": "diario",
                "active": True,
            }
        ]
        insumos = {
            1: {
                "name": "Ração Pro",
                "unit": "kg",
                "cost_per_unit": 1.50,
                "materia_seca_pct": 85.0,
            }
        }
        res = ingredientes_por_cabeca(planos, insumos, cabecas_no_piquete=20)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["nome"], "Ração Pro")
        self.assertEqual(res[0]["quantidade_kg_cabeca_dia"], 2.0)
        self.assertEqual(res[0]["custo_por_kg"], 1.50)
        self.assertEqual(res[0]["materia_seca_pct"], 85.0)

    def test_criterio_2_dois_planos_do_mesmo_insumo_somam(self):
        """Critério 2: Dois planos do mesmo insumo no mesmo piquete somam antes de virar uma linha."""
        planos = [
            {
                "insumo_id": 1,
                "quantity": 10.0,
                "unit": "kg",
                "frequency": "diario",
                "active": True,
            },
            {
                "insumo_id": 1,
                "quantity": 10.0,
                "unit": "kg",
                "frequency": "diario",
                "active": True,
            },
        ]
        insumos = {
            1: {
                "name": "Sal Mineral",
                "unit": "kg",
                "cost_per_unit": 3.00,
                "materia_seca_pct": 90.0,
            }
        }
        res = ingredientes_por_cabeca(planos, insumos, cabecas_no_piquete=10)
        self.assertEqual(len(res), 1)
        # (10 + 10) / 10 = 2.0 kg/cabeça/dia
        self.assertEqual(res[0]["quantidade_kg_cabeca_dia"], 2.0)

    def test_criterio_3_plano_inativo_e_ignorado(self):
        """Critério 3: Plano inativo (active=False) não aparece no resultado."""
        planos = [
            {
                "insumo_id": 1,
                "quantity": 20.0,
                "unit": "kg",
                "frequency": "diario",
                "active": False,
            }
        ]
        insumos = {
            1: {
                "name": "Milho Moído",
                "unit": "kg",
                "cost_per_unit": 1.20,
            }
        }
        res = ingredientes_por_cabeca(planos, insumos, cabecas_no_piquete=10)
        self.assertEqual(len(res), 0)

    def test_criterio_4_cabecas_zero_devolve_lista_vazia(self):
        """Critério 4: cabecas_no_piquete=0 devolve lista vazia, sem exceção."""
        planos = [
            {
                "insumo_id": 1,
                "quantity": 20.0,
                "unit": "kg",
                "frequency": "diario",
                "active": True,
            }
        ]
        insumos = {1: {"name": "Milho", "unit": "kg", "cost_per_unit": 1.0}}
        res = ingredientes_por_cabeca(planos, insumos, cabecas_no_piquete=0)
        self.assertEqual(res, [])

    def test_criterio_5_insumo_sem_materia_seca_gera_linha_com_zero(self):
        """Critério 5: Insumo sem materia_seca_pct gera linha com esse valor 0.0, sem quebrar."""
        planos = [
            {
                "insumo_id": 1,
                "quantity": 10.0,
                "unit": "kg",
                "frequency": "diario",
                "active": True,
            }
        ]
        insumos = {1: {"name": "Núcleo", "unit": "kg", "cost_per_unit": 4.0}}
        res = ingredientes_por_cabeca(planos, insumos, cabecas_no_piquete=5)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["materia_seca_pct"], 0.0)

    def test_criterio_6_integra_com_dieta_custo_por_cabeca_dia(self):
        """Critério 6: Resultado passado para dieta.custo_por_cabeca_dia() produz custo_dia > 0."""
        planos = [
            {
                "insumo_id": 1,
                "quantity": 40.0,
                "unit": "kg",
                "frequency": "diario",
                "active": True,
            }
        ]
        insumos = {
            1: {
                "name": "Ração Pro",
                "unit": "kg",
                "cost_per_unit": 1.50,
                "materia_seca_pct": 85.0,
            }
        }
        ingredientes = ingredientes_por_cabeca(planos, insumos, cabecas_no_piquete=20)
        res_dieta = custo_por_cabeca_dia(ingredientes)
        self.assertGreater(res_dieta["custo_dia"], 0.0)
        self.assertEqual(res_dieta["custo_dia"], 3.0)  # 2 kg/cabeca * 1.50 = 3.00

    def test_frequencia_desconhecida_e_ignorada(self):
        """Testa que frequência desconhecida (ex: quinzenal) pula o plano."""
        planos = [
            {
                "insumo_id": 1,
                "quantity": 50.0,
                "unit": "kg",
                "frequency": "quinzenal",
                "active": True,
            }
        ]
        insumos = {1: {"name": "Insumo X", "unit": "kg", "cost_per_unit": 2.0}}
        res = ingredientes_por_cabeca(planos, insumos, cabecas_no_piquete=10)
        self.assertEqual(len(res), 0)


if __name__ == "__main__":
    unittest.main()
