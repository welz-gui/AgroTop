import unittest

from services.clima_adaptador import localizacoes_para_previsao


class TestClimaAdaptador(unittest.TestCase):
    def test_coordenada_propria_tem_prioridade_sobre_fallback(self):
        resultado = localizacoes_para_previsao(
            [
                {
                    "id": "p1",
                    "nome": "Fazenda Norte",
                    "latitude": -12.1,
                    "longitude": -55.2,
                    "campo_ignorado": "valor",
                }
            ],
            farm_lat=-15.0,
            farm_lon=-56.0,
        )

        self.assertEqual(
            resultado,
            [
                {
                    "lat": -12.1,
                    "lon": -55.2,
                    "propriedades": [{"id": "p1", "nome": "Fazenda Norte"}],
                }
            ],
        )

    def test_coordenada_propria_incompleta_usa_fallback(self):
        resultado = localizacoes_para_previsao(
            [
                {
                    "id": "p1",
                    "nome": "Fazenda Sul",
                    "latitude": -12.1,
                    "longitude": None,
                }
            ],
            farm_lat=-15.0,
            farm_lon=-56.0,
        )

        self.assertEqual(resultado[0]["lat"], -15.0)
        self.assertEqual(resultado[0]["lon"], -56.0)

    def test_fallback_compartilhado_gera_uma_localizacao(self):
        propriedades = [
            {"id": "p1", "nome": "Fazenda A", "latitude": None, "longitude": None},
            {"id": "p2", "nome": "Fazenda B", "latitude": -13.0, "longitude": None},
        ]

        resultado = localizacoes_para_previsao(
            propriedades, farm_lat=-15.0, farm_lon=-56.0
        )

        self.assertEqual(
            resultado,
            [
                {
                    "lat": -15.0,
                    "lon": -56.0,
                    "propriedades": [
                        {"id": "p1", "nome": "Fazenda A"},
                        {"id": "p2", "nome": "Fazenda B"},
                    ],
                }
            ],
        )

    def test_coordenada_propria_compartilhada_gera_uma_localizacao(self):
        propriedades = [
            {"id": "p1", "nome": "Fazenda A", "latitude": -12.1, "longitude": -55.2},
            {"id": "p2", "nome": "Fazenda B", "latitude": -12.1, "longitude": -55.2},
        ]

        resultado = localizacoes_para_previsao(propriedades, None, None)

        self.assertEqual(len(resultado), 1)
        self.assertEqual(
            resultado[0]["propriedades"],
            [
                {"id": "p1", "nome": "Fazenda A"},
                {"id": "p2", "nome": "Fazenda B"},
            ],
        )

    def test_sem_coordenada_e_sem_fallback_fica_fora(self):
        propriedades = [
            {"id": "p1", "nome": "Sem local", "latitude": None, "longitude": None},
            {"id": "p2", "nome": "Localizada", "latitude": -12.1, "longitude": -55.2},
        ]

        resultado = localizacoes_para_previsao(propriedades, None, None)

        self.assertEqual(
            resultado,
            [
                {
                    "lat": -12.1,
                    "lon": -55.2,
                    "propriedades": [{"id": "p2", "nome": "Localizada"}],
                }
            ],
        )

    def test_lista_vazia_devolve_lista_vazia(self):
        self.assertEqual(localizacoes_para_previsao([], None, None), [])

    def test_ordem_dos_grupos_e_da_primeira_ocorrencia(self):
        propriedades = [
            {"id": "p1", "nome": "Primeira", "latitude": -13.0, "longitude": -56.0},
            {"id": "p2", "nome": "Segunda", "latitude": -12.0, "longitude": -55.0},
            {"id": "p3", "nome": "Terceira", "latitude": -13.0, "longitude": -56.0},
        ]

        resultado = localizacoes_para_previsao(propriedades, None, None)

        self.assertEqual(
            [(grupo["lat"], grupo["lon"]) for grupo in resultado],
            [(-13.0, -56.0), (-12.0, -55.0)],
        )
        self.assertEqual(
            resultado[0]["propriedades"],
            [
                {"id": "p1", "nome": "Primeira"},
                {"id": "p3", "nome": "Terceira"},
            ],
        )

    def test_coordenadas_zero_sao_validas(self):
        resultado = localizacoes_para_previsao(
            [{"id": "p1", "nome": "Origem", "latitude": 0.0, "longitude": 0.0}],
            farm_lat=-15.0,
            farm_lon=-56.0,
        )

        self.assertEqual(resultado[0]["lat"], 0.0)
        self.assertEqual(resultado[0]["lon"], 0.0)


if __name__ == "__main__":
    unittest.main()
