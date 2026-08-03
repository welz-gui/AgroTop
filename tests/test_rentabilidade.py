import inspect
import unittest

from services.rentabilidade import ranking_por_raca


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
