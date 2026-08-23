import inspect
import unittest

from services.rentabilidade import por_lote_de_venda, ranking_por_raca


def _ciclo(
    raca,
    peso_entrada=300.0,
    peso_saida=450.0,
    dias=150,
    custo_total=900.0,
    receita=1800.0,
):
    return {
        "raca": raca,
        "peso_entrada": peso_entrada,
        "peso_saida": peso_saida,
        "dias": dias,
        "custo_total": custo_total,
        "receita": receita,
    }


class TestRankingPorRaca(unittest.TestCase):
    def test_assinatura_do_contrato(self):
        parametros = list(inspect.signature(ranking_por_raca).parameters)

        self.assertEqual(parametros, ["ciclos"])

    def test_lucro_igual_com_gmd_e_lucro_por_arroba_diferentes(self):
        resultado = ranking_por_raca([
            _ciclo("Nelore"),
            _ciclo(
                "Angus",
                peso_saida=375.0,
                dias=50,
            ),
        ])

        por_raca = {linha["raca"]: linha for linha in resultado}
        self.assertEqual(
            por_raca["Nelore"]["lucro_por_cabeca"],
            por_raca["Angus"]["lucro_por_cabeca"],
        )
        self.assertEqual(por_raca["Nelore"]["gmd_medio"], 1.0)
        self.assertEqual(por_raca["Angus"]["gmd_medio"], 1.5)
        self.assertEqual(
            por_raca["Nelore"]["lucro_por_arroba_produzida"], 90.0
        )
        self.assertEqual(
            por_raca["Angus"]["lucro_por_arroba_produzida"], 180.0
        )

    def test_mais_lucrativa_por_cabeca_pode_nao_ser_por_arroba(self):
        resultado = ranking_por_raca([
            _ciclo("Nelore", custo_total=1000.0, receita=2000.0),
            _ciclo(
                "Angus",
                peso_saida=375.0,
                dias=50,
                custo_total=900.0,
                receita=1700.0,
            ),
        ])

        por_raca = {linha["raca"]: linha for linha in resultado}
        self.assertGreater(
            por_raca["Nelore"]["lucro_por_cabeca"],
            por_raca["Angus"]["lucro_por_cabeca"],
        )
        self.assertLess(
            por_raca["Nelore"]["lucro_por_arroba_produzida"],
            por_raca["Angus"]["lucro_por_arroba_produzida"],
        )
        self.assertEqual(resultado[0]["raca"], "Nelore")

    def test_lista_vazia(self):
        self.assertEqual(ranking_por_raca([]), [])

    def test_dias_zero_nao_divide_e_devolve_gmd_zero(self):
        resultado = ranking_por_raca([_ciclo("Nelore", dias=0)])

        self.assertEqual(resultado[0]["gmd_medio"], 0.0)

    def test_receita_zero_nao_divide_e_devolve_margem_zero(self):
        resultado = ranking_por_raca([
            _ciclo("Nelore", custo_total=100.0, receita=0.0)
        ])

        self.assertEqual(resultado[0]["margem"], 0.0)

    def test_agrega_animais_da_mesma_raca(self):
        resultado = ranking_por_raca([
            _ciclo("Nelore", custo_total=900.0, receita=1800.0),
            _ciclo("Nelore", custo_total=1200.0, receita=1800.0),
        ])

        self.assertEqual(resultado[0]["animais"], 2)
        self.assertEqual(resultado[0]["lucro_por_cabeca"], 750.0)
        self.assertEqual(resultado[0]["margem"], 0.4167)

    def test_ciclo_sem_receita_nao_entra(self):
        sem_desfecho = _ciclo("Ativa")
        sem_desfecho["receita"] = None

        self.assertEqual(ranking_por_raca([sem_desfecho]), [])


if __name__ == "__main__":
    unittest.main()


class TestMargemNegativa(unittest.TestCase):
    """Raça que dá prejuízo precisa APARECER como prejuízo.

    A spec 0017 dizia `margem: 0..1` e a primeira versão travava o valor em zero,
    o que fazia prejuízo parecer empate. O texto da spec estava errado; foi
    corrigido junto com o código.
    """

    def _ciclo(self, raca, custo, receita):
        return {"raca": raca, "peso_entrada": 300.0, "peso_saida": 450.0,
                "dias": 200, "custo_total": custo, "receita": receita}

    def test_prejuizo_produz_margem_negativa(self):
        r = ranking_por_raca([self._ciclo("Angus", 8000.0, 6000.0)])
        self.assertAlmostEqual(r[0]["margem"], -0.3333, places=4)

    def test_prejuizo_nao_se_confunde_com_empate(self):
        """O caso que motivou a correção: os dois davam 0.0 antes."""
        r = {x["raca"]: x for x in ranking_por_raca([
            self._ciclo("Empate", 6000.0, 6000.0),
            self._ciclo("Prejuizo", 8000.0, 6000.0),
        ])}
        self.assertEqual(r["Empate"]["margem"], 0.0)
        self.assertLess(r["Prejuizo"]["margem"], 0.0,
                        "prejuízo travado em zero: indistinguível de empatar")

    def test_lucro_por_arroba_tambem_pode_ser_negativo(self):
        r = ranking_por_raca([self._ciclo("Angus", 8000.0, 6000.0)])
        self.assertLess(r[0]["lucro_por_arroba_produzida"], 0.0)


def _venda(id, lot_ref=None, sale_date="2026-01-10", weight_kg=300.0,
           cost_at_sale=900.0, total_value=1500.0, profit=600.0,
           carcass_yield=0.52):
    return {"id": id, "lot_ref": lot_ref, "sale_date": sale_date,
            "weight_kg": weight_kg, "cost_at_sale": cost_at_sale,
            "total_value": total_value, "profit": profit,
            "carcass_yield": carcass_yield}


class TestPorLoteDeVenda(unittest.TestCase):
    def test_assinatura_do_contrato(self):
        parametros = list(inspect.signature(por_lote_de_venda).parameters)

        self.assertEqual(parametros, ["vendas"])

    def test_lista_vazia(self):
        self.assertEqual(por_lote_de_venda([]), [])

    def test_agrupa_por_lot_ref_somando_metricas(self):
        resultado = por_lote_de_venda([
            _venda(1, lot_ref="L1", weight_kg=300.0, cost_at_sale=900.0),
            _venda(2, lot_ref="L1", weight_kg=300.0, cost_at_sale=900.0),
        ])

        self.assertEqual(len(resultado), 1, "duas vendas do mesmo lote viraram dois lotes")
        lote = resultado[0]
        self.assertEqual(lote["lot_ref"], "L1")
        self.assertEqual(lote["animais"], 2)
        self.assertEqual(lote["peso_total_kg"], 600.0)
        self.assertEqual(lote["custo_total"], 1800.0)
        self.assertEqual(lote["receita_total"], 3000.0)
        self.assertEqual(lote["lucro_total"], 1200.0)

    def test_custo_por_kg_e_por_arroba_batem_com_a_conta_manual(self):
        # peso 600 kg, rendimento 52% -> 312 kg de carcaça -> 20.8 @
        resultado = por_lote_de_venda([
            _venda(1, lot_ref="L1", weight_kg=300.0, cost_at_sale=900.0,
                  carcass_yield=0.52),
            _venda(2, lot_ref="L1", weight_kg=300.0, cost_at_sale=900.0,
                  carcass_yield=0.52),
        ])

        lote = resultado[0]
        self.assertEqual(lote["custo_por_kg"], 3.0)          # 1800 / 600
        self.assertAlmostEqual(lote["custo_por_arroba"], 86.54, places=2)  # 1800 / 20.8

    def test_venda_sem_lot_ref_vira_lote_proprio_de_uma_cabeca(self):
        """Duas vendas avulsas (lot_ref=None) não podem se misturar só por
        terem a mesma chave nula — cada uma é o seu próprio lote de 1."""
        resultado = por_lote_de_venda([
            _venda(1, lot_ref=None, weight_kg=300.0),
            _venda(2, lot_ref=None, weight_kg=350.0),
        ])

        self.assertEqual(len(resultado), 2)
        self.assertTrue(all(r["animais"] == 1 for r in resultado))
        self.assertTrue(all(r["lot_ref"] is None for r in resultado))

    def test_venda_sem_id_e_sem_lot_ref(self):
        """Duas vendas ausentes de ID e lot_ref."""
        resultado = por_lote_de_venda([
            {"weight_kg": 100},
            {"weight_kg": 200},
        ])

        self.assertEqual(len(resultado), 2)
        self.assertTrue(all(r["animais"] == 1 for r in resultado))
        self.assertTrue(all(r["lot_ref"] is None for r in resultado))
        self.assertEqual(resultado[0]["peso_total_kg"], 100.0)
        self.assertEqual(resultado[1]["peso_total_kg"], 200.0)

    def test_peso_zero_nao_divide_por_zero(self):
        resultado = por_lote_de_venda([_venda(1, weight_kg=0.0)])

        lote = resultado[0]
        self.assertIsNone(lote["custo_por_kg"])
        self.assertIsNone(lote["custo_por_arroba"])

    def test_rendimento_ausente_usa_o_padrao_do_rebanho(self):
        """`carcass_yield=None` (join vazio com `animals`) não pode quebrar —
        cai no padrão de 52% como o resto do sistema (CARCASS_YIELD)."""
        resultado = por_lote_de_venda([
            _venda(1, weight_kg=300.0, cost_at_sale=900.0, carcass_yield=None),
        ])

        lote = resultado[0]
        self.assertIsNotNone(lote["custo_por_arroba"])
        # 300 kg * 52% / 15 = 10.4 @ ; 900 / 10.4 = 86.54
        self.assertAlmostEqual(lote["custo_por_arroba"], 86.54, places=2)
