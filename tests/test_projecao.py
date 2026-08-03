import inspect
import unittest

from services.projecao import (
    correlacao_chuva_gmd,
    projetar_abate,
    projetar_lote,
)


def _serie(chuvas, gmds):
    return [
        {
            "periodo": f"2026-{indice:02d}",
            "chuva_mm": chuva,
            "gmd_medio": gmd,
        }
        for indice, (chuva, gmd) in enumerate(zip(chuvas, gmds), start=1)
    ]


class TestProjetarAbate(unittest.TestCase):
    def test_assinaturas_do_contrato(self):
        self.assertEqual(
            list(inspect.signature(projetar_abate).parameters),
            ["peso_atual", "peso_alvo", "gmd", "hoje"],
        )
        self.assertEqual(
            list(inspect.signature(projetar_lote).parameters),
            ["animais", "hoje"],
        )
        self.assertEqual(
            list(inspect.signature(correlacao_chuva_gmd).parameters),
            ["series"],
        )

    def test_cem_dias_ate_o_alvo(self):
        resultado = projetar_abate(400, 500, 1.0, "2026-01-01")

        self.assertEqual(resultado, {
            "dias_restantes": 100,
            "data_prevista": "2026-04-11",
            "situacao": "projetado",
        })

    def test_dia_parcial_arredonda_para_cima(self):
        resultado = projetar_abate(499, 500, 0.6, "2026-01-01")

        self.assertEqual(resultado["dias_restantes"], 2)

    def test_animal_no_alvo_esta_pronto_hoje(self):
        resultado = projetar_abate(500, 500, 0, "2026-01-01")

        self.assertEqual(resultado, {
            "dias_restantes": 0,
            "data_prevista": "2026-01-01",
            "situacao": "pronto",
        })

    def test_gmd_zero_nao_projeta_data(self):
        resultado = projetar_abate(400, 500, 0, "2026-01-01")

        self.assertEqual(resultado, {
            "dias_restantes": None,
            "data_prevista": None,
            "situacao": "sem_ganho",
        })

    def test_gmd_negativo_indica_perda(self):
        resultado = projetar_abate(400, 500, -0.2, "2026-01-01")

        self.assertEqual(resultado, {
            "dias_restantes": None,
            "data_prevista": None,
            "situacao": "perdendo_peso",
        })


class TestProjetarLote(unittest.TestCase):
    def test_separa_sem_projecao_sem_inventar_gmd(self):
        animais = [
            {"id": "pronto", "peso_atual": 500, "peso_alvo": 500, "gmd": None},
            {"id": "projetado", "peso_atual": 490, "peso_alvo": 500, "gmd": 1},
            {"id": "parado", "peso_atual": 490, "peso_alvo": 500, "gmd": 0},
            {"id": "perdendo", "peso_atual": 490, "peso_alvo": 500, "gmd": -0.1},
        ]

        resultado = projetar_lote(animais, "2026-01-01")

        self.assertEqual(resultado, {
            "prontos": 1,
            "data_primeiro": "2026-01-01",
            "data_ultimo": "2026-01-11",
            "dias_ate_lote_completo": None,
            "sem_projecao": ["parado", "perdendo"],
        })

    def test_lote_inteiro_projetado_usa_a_ultima_data(self):
        animais = [
            {"id": "a", "peso_atual": 500, "peso_alvo": 500, "gmd": 0},
            {"id": "b", "peso_atual": 490, "peso_alvo": 500, "gmd": 1},
            {"id": "c", "peso_atual": 480, "peso_alvo": 500, "gmd": 1},
        ]

        resultado = projetar_lote(animais, "2026-01-01")

        self.assertEqual(resultado["dias_ate_lote_completo"], 20)
        self.assertEqual(resultado["data_ultimo"], "2026-01-21")
        self.assertEqual(resultado["sem_projecao"], [])

    def test_lote_vazio_nao_inventa_datas(self):
        self.assertEqual(projetar_lote([], "2026-01-01"), {
            "prontos": 0,
            "data_primeiro": None,
            "data_ultimo": None,
            "dias_ate_lote_completo": None,
            "sem_projecao": [],
        })


class TestCorrelacaoChuvaGmd(unittest.TestCase):
    def test_dois_periodos_sao_amostra_pequena(self):
        resultado = correlacao_chuva_gmd(_serie([10, 20], [0.4, 0.5]))

        self.assertIsNone(resultado["coeficiente"])
        self.assertEqual(resultado["n"], 2)
        self.assertIn("Amostra pequena", resultado["interpretacao"])

    def test_chuva_constante_nao_estoura(self):
        resultado = correlacao_chuva_gmd(_serie([10, 10, 10], [0.4, 0.5, 0.6]))

        self.assertIsNone(resultado["coeficiente"])
        self.assertIn("variação", resultado["interpretacao"])

    def test_pearson_positivo_e_negativo(self):
        positiva = correlacao_chuva_gmd(_serie([10, 20, 30], [0.4, 0.5, 0.6]))
        negativa = correlacao_chuva_gmd(_serie([10, 20, 30], [0.6, 0.5, 0.4]))

        self.assertAlmostEqual(positiva["coeficiente"], 1.0)
        self.assertAlmostEqual(negativa["coeficiente"], -1.0)
        self.assertIn("positiva", positiva["interpretacao"])
        self.assertIn("negativa", negativa["interpretacao"])
        self.assertIn("não demonstra causalidade", positiva["interpretacao"])

    def test_tres_e_doze_periodos_expressam_confianca_diferente(self):
        serie_tres = _serie([10, 20, 30], [0.4, 0.5, 0.6])
        serie_doze = _serie(
            list(range(10, 130, 10)),
            [0.40, 0.48, 0.45, 0.56, 0.62, 0.59, 0.70, 0.74, 0.71, 0.82, 0.86, 0.90],
        )

        interpretacao_tres = correlacao_chuva_gmd(serie_tres)["interpretacao"]
        interpretacao_doze = correlacao_chuva_gmd(serie_doze)["interpretacao"]

        self.assertIn("Amostra pequena", interpretacao_tres)
        self.assertIn("Em 12 períodos", interpretacao_doze)
        self.assertNotEqual(interpretacao_tres, interpretacao_doze)


if __name__ == "__main__":
    unittest.main()
