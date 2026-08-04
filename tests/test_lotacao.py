import unittest
from services.lotacao import (
    lotacao,
    capacidade,
    avaliar_lotacao,
    sobrepostos,
)


class TestLotacaoEGeometria(unittest.TestCase):
    def setUp(self):
        # Polígono de ~10 hectares em Alta Floresta-MT
        self.anel_10ha = [
            (-56.0000, -9.9000),
            (-56.0030, -9.9000),
            (-56.0030, -9.9030),
            (-56.0000, -9.9030),
            (-56.0000, -9.9000),
        ]

    def test_lotacao_dez_animais_450kg_em_dez_ha(self):
        animais = [{"id": f"A{i}", "peso": 450.0} for i in range(10)]
        res = lotacao(10.0, animais)

        self.assertEqual(res["cabecas"], 10)
        self.assertEqual(res["peso_total"], 4500.0)
        self.assertEqual(res["ua_total"], 10.0)
        self.assertEqual(res["ua_por_ha"], 1.0)

    def test_capacidade(self):
        cap = capacidade(10.0, 1.5)
        self.assertEqual(cap["ua_suportadas"], 15.0)
        self.assertEqual(cap["cabecas_450kg"], 15)

    def test_avaliar_lotacao_tolerancia(self):
        animais_10 = [{"id": f"A{i}", "peso": 450.0} for i in range(10)]

        # Lotação exatamente igual ao alvo (1.0 UA/ha em 10ha com 10 UAs)
        eval_exato = avaliar_lotacao(10.0, animais_10, 1.0)
        self.assertEqual(eval_exato["situacao"], "adequado")

        # 1% acima do alvo (1.01 UA/ha) -> deve continuar 'adequado' (tolerância +10%)
        animais_10_01 = [{"id": f"A{i}", "peso": 454.5} for i in range(10)]
        eval_1pct = avaliar_lotacao(10.0, animais_10_01, 1.0)
        self.assertEqual(eval_1pct["situacao"], "adequado")

        # Muito acima (+30% -> 1.3 UA/ha) -> 'sobrecarregado'
        animais_13 = [{"id": f"A{i}", "peso": 450.0} for i in range(13)]
        eval_sobre = avaliar_lotacao(10.0, animais_13, 1.0)
        self.assertEqual(eval_sobre["situacao"], "sobrecarregado")

        # Muito abaixo (0.5 UA/ha) -> 'ocioso'
        animais_5 = [{"id": f"A{i}", "peso": 450.0} for i in range(5)]
        eval_ocioso = avaliar_lotacao(10.0, animais_5, 1.0)
        self.assertEqual(eval_ocioso["situacao"], "ocioso")

    def test_sobrepostos_quadrados_identicos(self):
        piquetes = [
            {"id": "P1", "anel": self.anel_10ha},
            {"id": "P2", "anel": self.anel_10ha},
        ]
        res = sobrepostos(piquetes)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["a"], "P1")
        self.assertEqual(res[0]["b"], "P2")
        self.assertAlmostEqual(res[0]["pct_do_menor"], 100.0, delta=1.0)

    def test_sobrepostos_bordas_compartilhadas_nao_disparam(self):
        # Piquete A (ocidental)
        anel_a = [
            (-56.0030, -9.9000),
            (-56.0000, -9.9000),
            (-56.0000, -9.9030),
            (-56.0030, -9.9030),
            (-56.0030, -9.9000),
        ]
        # Piquete B encosta exatamente na borda leste do Piquete A (longitude -56.0000)
        anel_b = [
            (-56.0000, -9.9000),
            (-55.9970, -9.9000),
            (-55.9970, -9.9030),
            (-56.0000, -9.9030),
            (-56.0000, -9.9000),
        ]
        piquetes = [
            {"id": "PA", "anel": anel_a},
            {"id": "PB", "anel": anel_b},
        ]
        res = sobrepostos(piquetes)
        self.assertEqual(res, [])

    def test_area_zero_e_lista_vazia_nao_estouram(self):
        self.assertEqual(lotacao(0.0, [])["ua_por_ha"], 0.0)
        self.assertEqual(capacidade(0.0, 0.0)["ua_suportadas"], 0.0)
        self.assertEqual(
            avaliar_lotacao(0.0, [], 0.0)["situacao"], "adequado"
        )
        self.assertEqual(sobrepostos([]), [])

    def test_poligono_invalido_eh_pulado_sem_derrubar_os_demais(self):
        anel_invalido = [(-56.0, -9.9)]  # Menos de 3 vértices
        piquetes = [
            {"id": "P1", "anel": self.anel_10ha},
            {"id": "PINV", "anel": anel_invalido},
            {"id": "P2", "anel": self.anel_10ha},
        ]
        res = sobrepostos(piquetes)
        # PINV é ignorado, P1 e P2 continuam comparados com sucesso
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["a"], "P1")
        self.assertEqual(res[0]["b"], "P2")


if __name__ == "__main__":
    unittest.main()
