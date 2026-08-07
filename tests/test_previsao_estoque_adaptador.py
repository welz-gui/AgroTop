"""Testes unitários para services.previsao_estoque_adaptador (Spec 0039)."""

import unittest
from services.previsao_estoque_adaptador import (
    consumo_diario_planejado,
    montar_insumos,
)
from services.previsao_estoque import prever


def dummy_converter(qty, from_unit, to_unit):
    """Conversor de teste simples para unidades comuns."""
    if from_unit == to_unit:
        return float(qty)
    if from_unit == "g" and to_unit == "kg":
        return float(qty) / 1000.0
    if from_unit == "kg" and to_unit == "g":
        return float(qty) * 1000.0
    if from_unit == "saco":
        return None  # Unidade incompatível sem conversão
    return None


class TestPrevisaoEstoqueAdaptador(unittest.TestCase):

    def test_criterio_1_plano_diario_devolve_consumo_exato(self):
        """Critério 1: consumo_diario_planejado com plano diário de 2 kg/dia devolve 2.0."""
        insumos = {1: {"unit": "kg"}}
        planos = [
            {
                "insumo_id": 1,
                "quantity": 2.0,
                "unit": "kg",
                "frequency": "diario",
                "active": True,
            }
        ]
        res = consumo_diario_planejado(insumos, planos, dummy_converter)
        self.assertEqual(res, {1: 2.0})

    def test_criterio_2_unidade_incompativel_e_ignorada(self):
        """Critério 2: Plano com unidade incompatível (ex: saco vs kg) não contribui."""
        insumos = {1: {"unit": "kg"}}
        planos = [
            {
                "insumo_id": 1,
                "quantity": 10.0,
                "unit": "saco",
                "frequency": "diario",
                "active": True,
            }
        ]
        res = consumo_diario_planejado(insumos, planos, dummy_converter)
        self.assertEqual(res, {1: 0.0})

    def test_criterio_3_frequencia_desconhecida_e_ignorada(self):
        """Critério 3: Frequência fora de {"diario", "semanal", "mensal"} (ex: quinzenal) é ignorada.

        Garante a correção do defeito da primeira tentativa (PR #101).
        """
        insumos = {1: {"unit": "kg"}}
        planos = [
            {
                "insumo_id": 1,
                "quantity": 14.0,
                "unit": "kg",
                "frequency": "quinzenal",
                "active": True,
            },
            {
                "insumo_id": 1,
                "quantity": 30.0,
                "unit": "kg",
                "frequency": "",
                "active": True,
            },
            {
                "insumo_id": 1,
                "quantity": 5.0,
                "unit": "kg",
                "frequency": None,
                "active": True,
            },
        ]
        res = consumo_diario_planejado(insumos, planos, dummy_converter)
        self.assertEqual(res[1], 0.0)

    def test_frequencias_validas_semanal_e_mensal(self):
        """Testa conversão de frequências semanal (1/7) e mensal (1/30)."""
        insumos = {1: {"unit": "kg"}, 2: {"unit": "kg"}}
        planos = [
            {
                "insumo_id": 1,
                "quantity": 14.0,
                "unit": "kg",
                "frequency": "semanal",
                "active": True,
            },
            {
                "insumo_id": 2,
                "quantity": 60.0,
                "unit": "kg",
                "frequency": "mensal",
                "active": True,
            },
        ]
        res = consumo_diario_planejado(insumos, planos, dummy_converter)
        self.assertAlmostEqual(res[1], 2.0, places=4)
        self.assertAlmostEqual(res[2], 2.0, places=4)

    def test_criterio_4_montar_insumos_sem_prazo_reposicao_assume_zero(self):
        """Critério 4: montar_insumos sem prazos_de_reposicao produz prazo_reposicao_dias=0."""
        insumos_raw = [
            {
                "id": 10,
                "name": "Milho",
                "unit": "kg",
                "current_stock": 500.0,
                "min_stock": 100.0,
            }
        ]
        consumo_por_id = {10: 20.0}
        res = montar_insumos(insumos_raw, consumo_por_id)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["prazo_reposicao_dias"], 0)

    def test_criterio_5_insumo_sem_plano_ativo_possui_consumo_zero(self):
        """Critério 5: Insumo sem nenhum plano ativo aparece na lista final com consumo_diario=0.0."""
        insumos_raw = [
            {
                "id": 1,
                "name": "Sal Mineral",
                "unit": "kg",
                "current_stock": 50.0,
                "min_stock": 10.0,
            }
        ]
        consumo_por_id = consumo_diario_planejado({1: {"unit": "kg"}}, [], dummy_converter)
        res = montar_insumos(insumos_raw, consumo_por_id)
        self.assertEqual(res[0]["consumo_diario"], 0.0)

    def test_criterio_6_encadeamento_com_previsao_estoque_prever(self):
        """Critério 6: montar_insumos + previsao_estoque.prever produz urgencia 'critica' para saldo < min_stock."""
        insumos_raw = [
            {
                "id": 1,
                "name": "Ração Pro",
                "unit": "kg",
                "current_stock": 5.0,
                "min_stock": 50.0,
            }
        ]
        consumo_por_id = {1: 10.0}
        insumos_montados = montar_insumos(insumos_raw, consumo_por_id)

        resultado_previsao = prever(insumos_montados, "2026-08-06")
        self.assertEqual(len(resultado_previsao), 1)
        self.assertEqual(resultado_previsao[0]["urgencia"], "critica")


if __name__ == "__main__":
    unittest.main()
