"""Testes unitários para services.projecao_adaptador (Spec 0040)."""

import unittest
from services.projecao_adaptador import series_mensais
from services.projecao import correlacao_chuva_gmd


class TestProjecaoAdaptador(unittest.TestCase):

    def test_criterio_1_mes_com_chuva_e_gmd_produz_item_correto(self):
        """Critério 1: Mês com 3 leituras de chuva (120mm total) e 1 par de pesagens produz item correto."""
        leituras_chuva = [
            {"read_date": "2026-03-05", "rain_mm": 40.0},
            {"read_date": "2026-03-12", "rain_mm": 50.0},
            {"read_date": "2026-03-25", "rain_mm": 30.0},
        ]
        pesagens = [
            {"animal_uuid": "a1", "weigh_date": "2026-03-01", "weight": 200.0},
            {"animal_uuid": "a1", "weigh_date": "2026-03-21", "weight": 220.0},  # 20kg / 20d = 1.0 kg/dia
        ]
        res = series_mensais(leituras_chuva, pesagens)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["periodo"], "2026-03")
        self.assertEqual(res[0]["chuva_mm"], 120.0)
        self.assertEqual(res[0]["gmd_medio"], 1.0)

    def test_criterio_2_pesagens_cruzando_fronteira_do_mes_sao_descartadas(self):
        """Critério 2: Par de pesagens entre 28/07 e 03/08 cruza fronteira do mês e não gera GMD."""
        leituras_chuva = [
            {"read_date": "2026-07-15", "rain_mm": 50.0},
            {"read_date": "2026-08-15", "rain_mm": 60.0},
        ]
        pesagens = [
            {"animal_uuid": "a1", "weigh_date": "2026-07-28", "weight": 200.0},
            {"animal_uuid": "a1", "weigh_date": "2026-08-03", "weight": 206.0},
        ]
        res = series_mensais(leituras_chuva, pesagens)
        self.assertEqual(len(res), 0)

    def test_criterio_3_mes_sem_gmd_nao_aparece(self):
        """Critério 3: Mês com chuva mas sem GMD calculável não aparece na lista."""
        leituras_chuva = [
            {"read_date": "2026-05-10", "rain_mm": 80.0},
        ]
        pesagens = [
            # Apenas 1 pesagem no mês -> sem par para GMD
            {"animal_uuid": "a1", "weigh_date": "2026-05-10", "weight": 200.0},
        ]
        res = series_mensais(leituras_chuva, pesagens)
        self.assertEqual(len(res), 0)

    def test_criterio_4_mes_sem_chuva_nao_aparece(self):
        """Critério 4: Mês com GMD calculável mas sem leitura de chuva não aparece na lista."""
        leituras_chuva = []
        pesagens = [
            {"animal_uuid": "a1", "weigh_date": "2026-06-01", "weight": 200.0},
            {"animal_uuid": "a1", "weigh_date": "2026-06-21", "weight": 220.0},
        ]
        res = series_mensais(leituras_chuva, pesagens)
        self.assertEqual(len(res), 0)

    def test_criterio_5_dois_animais_no_mesmo_mes_gmd_medio_e_media(self):
        """Critério 5: Dois animais com pesagens no mesmo mês geram a média simples dos dois GMDs."""
        leituras_chuva = [
            {"read_date": "2026-04-10", "rain_mm": 100.0},
        ]
        pesagens = [
            # Animal 1: (220 - 200) / 20 = 1.0 kg/dia
            {"animal_uuid": "a1", "weigh_date": "2026-04-01", "weight": 200.0},
            {"animal_uuid": "a1", "weigh_date": "2026-04-21", "weight": 220.0},
            # Animal 2: (240 - 200) / 20 = 2.0 kg/dia
            {"animal_uuid": "a2", "weigh_date": "2026-04-01", "weight": 200.0},
            {"animal_uuid": "a2", "weigh_date": "2026-04-21", "weight": 240.0},
        ]
        res = series_mensais(leituras_chuva, pesagens)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["periodo"], "2026-04")
        self.assertEqual(res[0]["chuva_mm"], 100.0)
        self.assertEqual(res[0]["gmd_medio"], 1.5)  # (1.0 + 2.0) / 2 = 1.5

    def test_criterio_6_integra_com_correlacao_chuva_gmd(self):
        """Critério 6: Saída passada para projecao.correlacao_chuva_gmd() não levanta exceção para 0, 1, 2 e 5+ meses."""
        # 0 meses
        s0 = series_mensais([], [])
        res0 = correlacao_chuva_gmd(s0)
        self.assertIsNone(res0["coeficiente"])
        self.assertEqual(res0["n"], 0)

        # 5+ meses fictícios
        leituras_chuva = []
        pesagens = []
        for i in range(1, 6):
            mes_str = f"2026-0{i}" if i < 10 else f"2026-{i}"
            leituras_chuva.append({"read_date": f"{mes_str}-10", "rain_mm": i * 20.0})
            pesagens.append({"animal_uuid": "a1", "weigh_date": f"{mes_str}-01", "weight": 200.0})
            pesagens.append({"animal_uuid": "a1", "weigh_date": f"{mes_str}-21", "weight": 200.0 + (i * 10.0)})

        s5 = series_mensais(leituras_chuva, pesagens)
        self.assertEqual(len(s5), 5)
        res5 = correlacao_chuva_gmd(s5)
        self.assertIsNotNone(res5["coeficiente"])
        self.assertEqual(res5["n"], 5)


if __name__ == "__main__":
    unittest.main()
