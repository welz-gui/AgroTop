import unittest

from services.completude import avaliar_mes


def _pesagem(animal_id, data, lote_id="lote-1", method="balança"):
    return {
        "animal_id": animal_id,
        "data": data,
        "lote_id": lote_id,
        "method": method,
    }


class TestCompletudeMensal(unittest.TestCase):
    def test_mes_completo_e_regular(self):
        resultado = avaliar_mes(
            2026,
            1,
            2,
            [
                _pesagem("a", "2026-01-01"),
                _pesagem("a", "2026-01-31"),
                _pesagem("b", "2026-01-01"),
                _pesagem("b", "2026-01-31"),
            ],
            31,
            31,
            5,
            5,
        )

        for indicador in (
            "animais_com_pesagem_em_dia",
            "intervalos_uteis_gmd",
            "contexto_da_pesagem",
            "execucao_nutricional",
            "cobertura_ambiental",
        ):
            self.assertEqual(resultado[indicador], 1.0)
        self.assertEqual(resultado["alertas"], [])

    def test_metade_dos_animais_sem_pesagem_em_dia(self):
        resultado = avaliar_mes(
            2026,
            1,
            2,
            [_pesagem("a", "2026-01-31")],
            31,
            31,
            5,
            5,
        )

        self.assertEqual(resultado["animais_com_pesagem_em_dia"], 0.5)
        alerta = next(
            item
            for item in resultado["alertas"]
            if item["indicador"] == "animais_com_pesagem_em_dia"
        )
        self.assertEqual(alerta["valor"], 0.5)
        self.assertEqual(alerta["minimo"], 0.8)
        self.assertIn("Pese", alerta["mensagem"])

    def test_mes_sem_dados_retorna_zero_e_alertas(self):
        resultado = avaliar_mes(2026, 2, 0, [], 0, 0, 0, 0)

        for indicador in (
            "animais_com_pesagem_em_dia",
            "intervalos_uteis_gmd",
            "contexto_da_pesagem",
            "execucao_nutricional",
            "cobertura_ambiental",
        ):
            self.assertEqual(resultado[indicador], 0.0)
        self.assertEqual(len(resultado["alertas"]), 5)

    def test_intervalo_util_conta_animal_uma_vez_com_muitas_pesagens(self):
        resultado = avaliar_mes(
            2026,
            3,
            2,
            [
                _pesagem("a", "2026-01-31"),
                _pesagem("a", "2026-03-02"),
                _pesagem("a", "2026-03-20"),
                _pesagem("b", "2026-03-01"),
                _pesagem("b", "2026-03-15"),
            ],
            31,
            31,
            5,
            5,
        )

        self.assertEqual(resultado["intervalos_uteis_gmd"], 0.5)

    def test_janela_de_sessenta_dias_inclui_as_duas_bordas(self):
        resultado = avaliar_mes(
            2026,
            3,
            2,
            [
                _pesagem("dentro", "2026-01-30"),
                _pesagem("fora", "2026-01-29"),
            ],
            1,
            1,
            1,
            1,
        )

        self.assertEqual(resultado["animais_com_pesagem_em_dia"], 0.5)

    def test_contexto_exige_lote_e_metodo_preenchidos(self):
        resultado = avaliar_mes(
            2026,
            1,
            1,
            [
                _pesagem("a", "2026-01-01"),
                _pesagem("a", "2026-01-31", method=" "),
            ],
            1,
            1,
            1,
            1,
        )

        self.assertEqual(resultado["contexto_da_pesagem"], 0.5)

    def test_proporcoes_ficam_limitadas_a_um(self):
        resultado = avaliar_mes(
            2026,
            1,
            1,
            [
                _pesagem("a", "2026-01-01"),
                _pesagem("a", "2026-01-31"),
                _pesagem("b", "2026-01-31"),
            ],
            1,
            2,
            1,
            1,
        )

        self.assertEqual(resultado["animais_com_pesagem_em_dia"], 1.0)
        self.assertEqual(resultado["execucao_nutricional"], 1.0)


if __name__ == "__main__":
    unittest.main()
