import unittest

from services.completude import avaliar_mes
from services.completude_adaptador import janela_do_mes, normalizar_pesagens


class TestCompletudeAdaptador(unittest.TestCase):
    def test_normaliza_os_campos_reais_de_weighings(self):
        pesagens = [
            {
                "animal_uuid": "a1",
                "weight": 420.5,
                "weigh_date": "2024-03-15",
                "lote_id": "l1",
                "method": "balanca",
            }
        ]

        self.assertEqual(
            normalizar_pesagens(pesagens),
            [
                {
                    "animal_id": "a1",
                    "data": "2024-03-15",
                    "lote_id": "l1",
                    "method": "balanca",
                }
            ],
        )

    def test_quatro_checagens_contam_planejadas_e_so_feito_executa(self):
        resultado = janela_do_mes(
            2024,
            3,
            checagens_de_trato=[
                {"status": "feito"},
                {"status": "parcial"},
                {"status": "nao_feito"},
                {"status": "feito"},
            ],
            leituras_de_chuva=[],
        )

        self.assertEqual(resultado["dias_lote_planejados"], 4)
        self.assertEqual(resultado["dias_lote_executados"], 2)

    def test_mes_sem_chuva_mantem_denominador_real(self):
        resultado = janela_do_mes(
            2024,
            3,
            checagens_de_trato=[],
            leituras_de_chuva=[],
        )

        self.assertEqual(resultado["semanas_com_chuva"], 0)
        self.assertEqual(resultado["semanas_no_mes"], 5)

    def test_fevereiro_comum_e_bissexto_podem_cruzar_semanas_diferentes(self):
        comum = janela_do_mes(
            2021, 2, checagens_de_trato=[], leituras_de_chuva=[]
        )
        bissexto = janela_do_mes(
            2024, 2, checagens_de_trato=[], leituras_de_chuva=[]
        )

        self.assertEqual(comum["semanas_no_mes"], 4)
        self.assertEqual(bissexto["semanas_no_mes"], 5)
        self.assertNotEqual(comum["semanas_no_mes"], 0)
        self.assertNotEqual(bissexto["semanas_no_mes"], 0)

    def test_chuva_usa_semana_iso_e_ignora_leitura_fora_do_mes(self):
        resultado = janela_do_mes(
            2024,
            3,
            checagens_de_trato=[],
            leituras_de_chuva=[
                {"read_date": "2024-03-01", "rain_mm": 2.0},
                {"read_date": "2024-03-07", "rain_mm": 0.0},
                {"read_date": "2024-03-20", "rain_mm": 0.5},
                {"read_date": "2024-04-01", "rain_mm": 12.0},
            ],
        )

        self.assertEqual(resultado["semanas_com_chuva"], 2)

    def test_listas_vazias_nao_estouram(self):
        self.assertEqual(normalizar_pesagens([]), [])
        self.assertEqual(
            janela_do_mes(2024, 1, checagens_de_trato=[], leituras_de_chuva=[]),
            {
                "dias_lote_planejados": 0,
                "dias_lote_executados": 0,
                "semanas_com_chuva": 0,
                "semanas_no_mes": 5,
            },
        )

    def test_funcoes_encadeadas_com_avaliar_mes_produzem_alerta(self):
        pesagens = normalizar_pesagens(
            [
                {"animal_uuid": "a1", "weigh_date": "2024-03-15", "lote_id": "l1", "method": "balanca"},
                {"animal_uuid": "a1", "weigh_date": "2024-01-30", "lote_id": "l1", "method": "balanca"},
                {"animal_uuid": "a2", "weigh_date": "2024-03-10", "lote_id": "l1", "method": "balanca"},
            ]
        )
        janela = janela_do_mes(
            2024,
            3,
            checagens_de_trato=[{"status": "feito"}, {"status": "nao_feito"}],
            leituras_de_chuva=[{"read_date": "2024-03-05", "rain_mm": 1.0}],
        )

        resultado = avaliar_mes(
            2024,
            3,
            animais_ativos=4,
            pesagens=pesagens,
            **janela,
        )

        self.assertIn("alertas", resultado)
        self.assertTrue(resultado["alertas"])


if __name__ == "__main__":
    unittest.main()
