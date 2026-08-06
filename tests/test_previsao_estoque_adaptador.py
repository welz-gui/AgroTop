"""Testes unitários do adaptador de previsão de estoque (Spec 0039)."""

import unittest
from services import previsao_estoque, previsao_estoque_adaptador


def _mock_converter(quantidade: float, unidade_origem: str, unidade_destino: str):
    """Função mock de conversão de quantidade para testes sem banco de dados."""
    if unidade_origem == unidade_destino:
        return float(quantidade)
    if unidade_origem == "g" and unidade_destino == "kg":
        return float(quantidade) / 1000.0
    if unidade_origem == "kg" and unidade_destino == "g":
        return float(quantidade) * 1000.0
    if unidade_origem == "saco" and unidade_destino == "kg":
        return None  # Unidade incompatível sem conversão conhecida
    return float(quantidade)


class TestPrevisaoEstoqueAdaptador(unittest.TestCase):
    def test_consumo_diario_planejado_plano_diario(self):
        """Critério 1: plano diário de 2 kg/dia devolve 2.0 para aquele insumo."""
        insumos_por_id = {1: {"id": 1, "unit": "kg"}}
        planos_ativos = [
            {"insumo_id": 1, "quantity": 2.0, "unit": "kg", "frequency": "diario"}
        ]

        res = previsao_estoque_adaptador.consumo_diario_planejado(
            insumos_por_id, planos_ativos, _mock_converter
        )

        self.assertEqual(res, {1: 2.0})

    def test_unidade_incompativel_e_ignorada(self):
        """Critério 2: plano com unidade incompatível (ex.: saco vs kg) é ignorado sem erro."""
        insumos_por_id = {1: {"id": 1, "unit": "kg"}}
        planos_ativos = [
            {"insumo_id": 1, "quantity": 1.0, "unit": "saco", "frequency": "diario"}
        ]

        res = previsao_estoque_adaptador.consumo_diario_planejado(
            insumos_por_id, planos_ativos, _mock_converter
        )

        self.assertEqual(res, {})

    def test_montar_insumos_sem_prazos_de_reposicao(self):
        """Critério 3: montar_insumos sem prazos_de_reposicao produz prazo_reposicao_dias=0."""
        insumos = [
            {"id": 1, "name": "Milho", "unit": "kg", "current_stock": 500.0, "min_stock": 100.0}
        ]
        consumo_por_id = {1: 10.0}

        res = previsao_estoque_adaptador.montar_insumos(insumos, consumo_por_id)

        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["prazo_reposicao_dias"], 0)

    def test_insumo_sem_plano_ativo_tem_consumo_zero(self):
        """Critério 4: insumo sem plano ativo aparece na lista final com consumo_diario=0.0."""
        insumos = [
            {"id": 1, "name": "Sal Mineral", "unit": "kg", "current_stock": 50.0, "min_stock": 20.0}
        ]
        consumo_por_id = {}  # Nenhum plano ativo para insumo 1

        res = previsao_estoque_adaptador.montar_insumos(insumos, consumo_por_id)

        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["consumo_diario"], 0.0)

    def test_encadeamento_com_previsao_estoque_prever_critica(self):
        """Critério 5: o resultado de montar_insumos encadeado com previsao_estoque.prever()
        produz urgencia='critica' para saldo < estoque_minimo.
        """
        insumos = [
            {"id": 1, "name": "Ração", "unit": "kg", "current_stock": 50.0, "min_stock": 100.0}
        ]
        insumos_por_id = {1: {"id": 1, "unit": "kg"}}
        planos_ativos = []  # Sem consumo registrado

        consumo_dict = previsao_estoque_adaptador.consumo_diario_planejado(
            insumos_por_id, planos_ativos, _mock_converter
        )
        lista_montada = previsao_estoque_adaptador.montar_insumos(
            insumos, consumo_dict
        )
        previsao = previsao_estoque.prever(lista_montada, "2026-08-06")

        self.assertEqual(len(previsao), 1)
        self.assertEqual(previsao[0]["urgencia"], "critica")

    def test_frequencias_variadas_e_multiplos_planos(self):
        """Testa cálculo de consumo para frequências diária, semanal e mensal para o mesmo insumo."""
        insumos_por_id = {1: {"id": 1, "unit": "kg"}}
        planos_ativos = [
            {"insumo_id": 1, "quantity": 10.0, "unit": "kg", "frequency": "diario"},
            {"insumo_id": 1, "quantity": 14.0, "unit": "kg", "frequency": "semanal"},  # +2 kg/dia
            {"insumo_id": 1, "quantity": 30.0, "unit": "kg", "frequency": "mensal"},   # +1 kg/dia
        ]

        res = previsao_estoque_adaptador.consumo_diario_planejado(
            insumos_por_id, planos_ativos, _mock_converter
        )

        self.assertAlmostEqual(res[1], 13.0, places=4)

    def test_suporta_prazos_de_reposicao_customizados(self):
        """Testa o repasse correto do prazo de reposição quando informado."""
        insumos = [
            {"id": 1, "name": "Farelo", "unit": "kg", "current_stock": 1000.0, "min_stock": 200.0}
        ]
        consumo_por_id = {1: 50.0}
        prazos = {1: 7}

        res = previsao_estoque_adaptador.montar_insumos(
            insumos, consumo_por_id, prazos
        )

        self.assertEqual(res[0]["prazo_reposicao_dias"], 7)


if __name__ == "__main__":
    unittest.main()
