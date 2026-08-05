"""Testes unitários para services/lotacao.py (Spec 0028)."""

import unittest
from services import lotacao


class TestLotacao(unittest.TestCase):
    def test_dez_animais_450kg_em_10ha_da_uma_ua_por_ha(self):
        """Critério 1: Dez animais de 450 kg em 10 ha dão exatamente ua_por_ha = 1.0."""
        animais = [{"id": str(i), "peso": 450.0} for i in range(10)]
        res = lotacao.lotacao(10.0, animais)

        self.assertEqual(res["cabecas"], 10)
        self.assertEqual(res["peso_total"], 4500.0)
        self.assertEqual(res["ua_total"], 10.0)
        self.assertEqual(res["ua_por_ha"], 1.0)

    def test_lista_vazia_e_area_zero_nao_dividem_por_zero(self):
        """Critério 5: Área zero e lista vazia não estouram nem dividem por zero."""
        res_vazia = lotacao.lotacao(10.0, [])
        self.assertEqual(res_vazia["ua_total"], 0.0)
        self.assertEqual(res_vazia["ua_por_ha"], 0.0)
        self.assertEqual(res_vazia["cabecas"], 0)

        res_area_zero = lotacao.lotacao(0.0, [{"id": "1", "peso": 450.0}])
        self.assertEqual(res_area_zero["ua_por_ha"], 0.0)
        self.assertEqual(res_area_zero["ua_total"], 1.0)

        cap_zero = lotacao.capacidade(0.0, 1.5)
        self.assertEqual(cap_zero["ua_suportadas"], 0.0)
        self.assertEqual(cap_zero["cabecas_450kg"], 0)


class TestCapacidade(unittest.TestCase):
    def test_calculo_capacidade_basico(self):
        res = lotacao.capacidade(10.0, 1.5)
        self.assertEqual(res["ua_suportadas"], 15.0)
        self.assertEqual(res["cabecas_450kg"], 15)


class TestAvaliarLotacao(unittest.TestCase):
    def test_avaliar_lotacao_tolerancia_adequadas(self):
        """Critério 2: avaliar_lotacao com atual igual ao alvo devolve adequado, e 1 % acima também."""
        animais_alvo = [{"id": str(i), "peso": 450.0} for i in range(10)]  # 10 UA em 10 ha = 1.0 UA/ha

        # Atual igual ao alvo (1.0 vs 1.0)
        res_exato = lotacao.avaliar_lotacao(10.0, animais_alvo, 1.0)
        self.assertEqual(res_exato["situacao"], "adequado")

        # 1 % acima do alvo (1.01 UA/ha vs alvo 1.0)
        animais_1pct_acima = [{"id": str(i), "peso": 454.5} for i in range(10)]  # 4545 kg total = 10.1 UA em 10 ha = 1.01 UA/ha
        res_1pct = lotacao.avaliar_lotacao(10.0, animais_1pct_acima, 1.0)
        self.assertEqual(res_1pct["situacao"], "adequado")

    def test_avaliar_lotacao_ocioso_e_sobrecarregado(self):
        # 20 % abaixo do alvo -> ocioso
        animais_poucos = [{"id": str(i), "peso": 450.0} for i in range(7)]  # 0.7 UA/ha vs 1.0
        res_ocioso = lotacao.avaliar_lotacao(10.0, animais_poucos, 1.0)
        self.assertEqual(res_ocioso["situacao"], "ocioso")

        # 20 % acima do alvo -> sobrecarregado
        animais_muitos = [{"id": str(i), "peso": 450.0} for i in range(13)]  # 1.3 UA/ha vs 1.0
        res_sobre = lotacao.avaliar_lotacao(10.0, animais_muitos, 1.0)
        self.assertEqual(res_sobre["situacao"], "sobrecarregado")


class TestSobrepostos(unittest.TestCase):
    def test_quadrados_em_zonas_utm_diferentes_nao_sao_sobrepostos(self):
        """Teste obrigatório: dois quadrados na mesma latitude em zonas UTM diferentes (lon -55 e lon -49)
        não devem ser reportados como sobrepostos.
        """
        # Quadrado A na zona UTM 21 (lon -55.0)
        quadrado_a = [
            (-55.000, -15.000),
            (-55.001, -15.000),
            (-55.001, -15.001),
            (-55.000, -15.001),
        ]
        # Quadrado B na zona UTM 22 (lon -49.0) com mesmas dimensões angulares locais
        quadrado_b = [
            (-49.000, -15.000),
            (-49.001, -15.000),
            (-49.001, -15.001),
            (-49.000, -15.001),
        ]

        piquetes = [
            {"id": "A", "anel": quadrado_a},
            {"id": "B", "anel": quadrado_b},
        ]

        res = lotacao.sobrepostos(piquetes)
        self.assertEqual(res, [], "Piquetes a 500+ km de distância não podem ser reportados como sobrepostos")

    def test_dois_quadrados_identicos_sobrepostos_100_porcento(self):
        """Critério 3: Dois quadrados idênticos são detectados com pct_do_menor próximo de 100."""
        quadrado = [
            (-55.000, -15.000),
            (-55.002, -15.000),
            (-55.002, -15.002),
            (-55.000, -15.002),
        ]
        piquetes = [
            {"id": "P1", "anel": quadrado},
            {"id": "P2", "anel": quadrado},
        ]
        res = lotacao.sobrepostos(piquetes)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["a"], "P1")
        self.assertEqual(res[0]["b"], "P2")
        self.assertAlmostEqual(res[0]["pct_do_menor"], 100.0, delta=0.5)

    def test_quadrados_que_so_encostam_na_borda_nao_sao_reportados(self):
        """Critério 4: Dois quadrados que só encostam na borda não aparecem na lista."""
        q1 = [
            (-55.000, -15.000),
            (-55.001, -15.000),
            (-55.001, -15.001),
            (-55.000, -15.001),
        ]
        # q2 compartilha a borda lon = -55.001
        q2 = [
            (-55.001, -15.000),
            (-55.002, -15.000),
            (-55.002, -15.001),
            (-55.001, -15.001),
        ]
        piquetes = [
            {"id": "P1", "anel": q1},
            {"id": "P2", "anel": q2},
        ]
        res = lotacao.sobrepostos(piquetes)
        self.assertEqual(res, [])

    def test_poligono_invalido_e_pulado_sem_derrubar_demais(self):
        """Critério 6: Polígono inválido é pulado com registro, não derruba a checagem dos demais."""
        valido1 = [
            (-55.000, -15.000),
            (-55.002, -15.000),
            (-55.002, -15.002),
            (-55.000, -15.002),
        ]
        invalido = [
            (-55.000, -15.000),  # Menos de 3 vértices
            (-55.001, -15.001),
        ]
        valido2 = list(valido1)

        piquetes = [
            {"id": "V1", "anel": valido1},
            {"id": "INV", "anel": invalido},
            {"id": "V2", "anel": valido2},
        ]
        res = lotacao.sobrepostos(piquetes)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["a"], "V1")
        self.assertEqual(res[0]["b"], "V2")

    def test_lista_vazia_sobrepostos(self):
        self.assertEqual(lotacao.sobrepostos([]), [])
        self.assertEqual(lotacao.sobrepostos([{"id": "1", "anel": []}]), [])
