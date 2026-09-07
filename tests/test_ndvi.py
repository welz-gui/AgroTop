"""Testes unitários para o módulo de NDVI por satélite (Spec 0079).

Cobre:
1. Cálculo do maior vão em dias com bordas do período (início até 1ª cena,
   entre cenas, última até fim).
2. Cálculo puro de NDVI com máscara SCL e escala/offset.
3. Busca STAC e tratamento de indisponibilidade de rede
   (NdviIndisponivelError).
4. Função principal `ndvi_do_piquete` com cenas utilizáveis e zero cenas.
5. Ausência de credenciais/chaves de API hardcoded.
6. Renderização da UI em `app.py` (aviso permanente e sem polígono).
"""

from datetime import date
import os
import re
import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from shapely.geometry import Polygon

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import app  # noqa: E402
from services.ndvi import (  # noqa: E402
    calcular_maior_vao,
    calcular_ndvi_cena,
    buscar_cenas_stac,
    ndvi_do_piquete,
    NdviIndisponivelError,
    NdviResultado,
)


class TestMaiorVao(unittest.TestCase):
    """Testa o cálculo do maior vão em dias, incluindo bordas."""

    def test_sem_cenas_vao_e_o_periodo_inteiro(self):
        inicio = date(2025, 5, 1)
        fim = date(2026, 4, 30)
        esperado = (fim - inicio).days
        self.assertEqual(calcular_maior_vao([], inicio, fim), esperado)

    def test_inicio_maior_que_fim_retorna_zero(self):
        self.assertEqual(
            calcular_maior_vao([], date(2026, 1, 1), date(2025, 1, 1)), 0
        )

    def test_inicio_igual_fim_sem_cenas_retorna_zero(self):
        self.assertEqual(
            calcular_maior_vao([], date(2026, 1, 1), date(2026, 1, 1)), 0
        )

    def test_uma_cena_no_meio_inclui_bordas(self):
        inicio = date(2025, 5, 1)
        fim = date(2026, 4, 30)
        # Cena no 9º dia (10/05/2025).
        # Vão do início até a cena: 9 dias.
        # Vão da cena até o fim: 355 dias.
        datas = [date(2025, 5, 10)]
        self.assertEqual(calcular_maior_vao(datas, inicio, fim), 355)

    def test_cenas_com_maior_vao_entre_elas(self):
        inicio = date(2025, 5, 1)
        fim = date(2025, 7, 15)
        # Início (01/05) -> cena 1 (05/05): 4 dias
        # Cena 1 (05/05) -> cena 2 (10/07): 66 dias
        # Cena 2 (10/07) -> fim (15/07): 5 dias
        datas = [date(2025, 5, 5), date(2025, 7, 10)]
        self.assertEqual(calcular_maior_vao(datas, inicio, fim), 66)

    def test_ignora_duplicadas_e_fora_do_intervalo(self):
        inicio = date(2025, 5, 1)
        fim = date(2025, 5, 31)
        datas = [
            date(2025, 4, 1),   # fora (antes)
            date(2025, 5, 10),
            date(2025, 5, 10),  # duplicada
            date(2025, 5, 20),
            date(2025, 6, 1),   # fora (depois)
        ]
        # Intervalos: 01/05 a 10/05 (9d), 10 a 20 (10d), 20 a 31 (11d)
        self.assertEqual(calcular_maior_vao(datas, inicio, fim), 11)


class TestCalcularNdviCena(unittest.TestCase):
    """Testa a função de cálculo de NDVI em arrays recortados."""

    def setUp(self):
        self.poligono = Polygon([
            (-55.90, -13.30),
            (-55.90, -13.29),
            (-55.89, -13.29),
            (-55.89, -13.30),
            (-55.90, -13.30),
        ])
        self.assets = {
            "red": {
                "href": "https://fake.aws.com/B04.tif",
                "raster:bands": [{"scale": 0.0001, "offset": 0.0}],
            },
            "nir": {
                "href": "https://fake.aws.com/B08.tif",
                "raster:bands": [{"scale": 0.0001, "offset": 0.0}],
            },
            "scl": {
                "href": "https://fake.aws.com/SCL.tif",
                "raster:bands": [{"scale": 1.0, "offset": 0.0}],
            },
        }

    @patch("services.ndvi.WarpedVRT")
    @patch("services.ndvi.mask")
    @patch("services.ndvi.rasterio.open")
    @patch("services.ndvi.rasterio.Env")
    def test_calculo_correto_com_pixels_validos(
        self, mock_env, mock_open, mock_mask, mock_vrt
    ):
        mock_src = MagicMock()
        mock_src.crs = "EPSG:4326"
        mock_open.return_value.__enter__.return_value = mock_src
        mock_vrt.return_value.__enter__.return_value = mock_src

        # Dois pixels válidos (SCL = 4 vegetação, SCL = 5 solo)
        # Pixel 1: red=1000 (0.1), nir=5000 (0.5) -> (0.5-0.1)/(0.5+0.1)=0.6667
        # Pixel 2: red=2000 (0.2), nir=6000 (0.6) -> (0.6-0.2)/(0.6+0.2)=0.5000
        # Média = (0.6667 + 0.5) / 2 = 0.5833
        red_arr = np.array([[[1000, 2000]]], dtype=np.int16)
        nir_arr = np.array([[[5000, 6000]]], dtype=np.int16)
        scl_arr = np.array([[[4, 5]]], dtype=np.uint8)

        mock_mask.side_effect = [
            (red_arr, None),
            (nir_arr, None),
            (scl_arr, None),
        ]

        ndvi = calcular_ndvi_cena(self.assets, self.poligono)
        self.assertAlmostEqual(ndvi, 0.5833, places=3)

    @patch("services.ndvi.WarpedVRT")
    @patch("services.ndvi.mask")
    @patch("services.ndvi.rasterio.open")
    @patch("services.ndvi.rasterio.Env")
    def test_mascara_scl_exclui_nuvem_e_sombra(
        self, mock_env, mock_open, mock_mask, mock_vrt
    ):
        mock_src = MagicMock()
        mock_src.crs = "EPSG:4326"
        mock_open.return_value.__enter__.return_value = mock_src
        mock_vrt.return_value.__enter__.return_value = mock_src

        # SCL = 8 (nuvem média) e SCL = 3 (sombra) -> nenhum pixel válido
        red_arr = np.array([[[1000, 2000]]], dtype=np.int16)
        nir_arr = np.array([[[5000, 6000]]], dtype=np.int16)
        scl_arr = np.array([[[8, 3]]], dtype=np.uint8)

        mock_mask.side_effect = [
            (red_arr, None),
            (nir_arr, None),
            (scl_arr, None),
        ]

        with self.assertRaises(ValueError) as ctx:
            calcular_ndvi_cena(self.assets, self.poligono)
        self.assertIn("Nenhum pixel de superfície válido", str(ctx.exception))

    def test_ativo_ausente_lanca_value_error(self):
        assets_incompletos = {
            "red": {"href": "https://fake.aws.com/B04.tif"},
        }
        with self.assertRaises(ValueError):
            calcular_ndvi_cena(assets_incompletos, self.poligono)

    @patch("services.ndvi.rasterio.open")
    @patch("services.ndvi.rasterio.Env")
    def test_erro_de_leitura_lanca_ndvi_indisponivel(
        self, mock_env, mock_open
    ):
        mock_open.side_effect = OSError("Connection timed out reading COG")
        with self.assertRaises(NdviIndisponivelError):
            calcular_ndvi_cena(self.assets, self.poligono)


class TestBuscarCenasStac(unittest.TestCase):
    """Testa a integração com a API STAC Earth Search v1."""

    def setUp(self):
        self.coords = [
            (-55.90, -13.30),
            (-55.90, -13.29),
            (-55.89, -13.29),
            (-55.89, -13.30),
            (-55.90, -13.30),
        ]

    @patch("services.ndvi.requests.post")
    def test_busca_com_sucesso(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "features": [
                {
                    "id": "S2A_20250510",
                    "properties": {
                        "datetime": "2025-05-10T14:00:00Z",
                        "eo:cloud_cover": 12.5,
                    },
                    "assets": {"red": {"href": "http://cog/red.tif"}},
                },
                {
                    "id": "S2B_20250515",
                    "properties": {
                        "datetime": "2025-05-15T14:00:00Z",
                        "eo:cloud_cover": 85.0,
                    },
                    "assets": {"red": {"href": "http://cog/red2.tif"}},
                },
            ]
        }
        mock_post.return_value = mock_resp

        cenas = buscar_cenas_stac(
            self.coords, date(2025, 5, 1), date(2025, 5, 31)
        )
        self.assertEqual(len(cenas), 2)
        self.assertEqual(cenas[0]["scene_id"], "S2A_20250510")
        self.assertEqual(cenas[0]["date"], date(2025, 5, 10))
        self.assertEqual(cenas[0]["cloud_cover"], 12.5)

    @patch("services.ndvi.requests.post")
    def test_falha_de_rede_lanca_ndvi_indisponivel(self, mock_post):
        import requests
        mock_post.side_effect = requests.ConnectionError("Sem conexao")
        with self.assertRaises(NdviIndisponivelError):
            buscar_cenas_stac(
                self.coords, date(2025, 5, 1), date(2025, 5, 31)
            )


class TestNdviDoPiquete(unittest.TestCase):
    """Testa a orquestração da busca de cenas e cálculo da série."""

    def setUp(self):
        self.coords = [
            (-55.90, -13.30),
            (-55.90, -13.29),
            (-55.89, -13.29),
            (-55.89, -13.30),
            (-55.90, -13.30),
        ]

    def test_poligono_invalido_lanca_value_error(self):
        with self.assertRaises(ValueError):
            ndvi_do_piquete([], date(2025, 5, 1), date(2025, 5, 31))

    def test_inicio_apos_fim_lanca_value_error(self):
        with self.assertRaises(ValueError):
            ndvi_do_piquete(self.coords, date(2025, 6, 1), date(2025, 5, 1))

    @patch("services.ndvi.calcular_ndvi_cena")
    @patch("services.ndvi.buscar_cenas_stac")
    def test_cenas_utilizaveis_simples(self, mock_stac, mock_calc):
        mock_stac.return_value = [
            {
                "scene_id": "S2_01",
                "date": date(2025, 5, 10),
                "cloud_cover": 5.0,
                "assets": {"red": {}, "nir": {}, "scl": {}},
            },
            {
                "scene_id": "S2_02",
                "date": date(2025, 5, 20),
                "cloud_cover": 15.0,
                "assets": {"red": {}, "nir": {}, "scl": {}},
            },
            {
                "scene_id": "S2_03",
                "date": date(2025, 5, 25),
                "cloud_cover": 75.0,  # acima do limiar de 20%
                "assets": {"red": {}, "nir": {}, "scl": {}},
            },
        ]
        mock_calc.side_effect = [0.65, 0.70]

        inicio = date(2025, 5, 1)
        fim = date(2025, 5, 31)
        res = ndvi_do_piquete(self.coords, inicio, fim, nuvem_max_pct=20)

        self.assertIsInstance(res, NdviResultado)
        self.assertEqual(res.total_cenas_buscadas, 3)
        self.assertEqual(res.total_cenas_utilizaveis, 2)
        self.assertEqual(len(res.serie), 2)
        self.assertEqual(res.serie[0].ndvi_medio, 0.65)
        self.assertEqual(res.serie[0].id_da_cena, "S2_01")
        self.assertEqual(res.serie[1].ndvi_medio, 0.70)
        self.assertEqual(res.serie[1].id_da_cena, "S2_02")

        # Vãos: 01/05 -> 10/05 (9d), 10/05 -> 20/05 (10d), 20/05 -> 31/05 (11d)
        self.assertEqual(res.maior_vao_dias, 11)

    @patch("services.ndvi.buscar_cenas_stac")
    def test_zero_cenas_utilizaveis_retorna_serie_vazia(self, mock_stac):
        mock_stac.return_value = [
            {
                "scene_id": "S2_01",
                "date": date(2025, 11, 10),
                "cloud_cover": 90.0,
                "assets": {},
            },
            {
                "scene_id": "S2_02",
                "date": date(2025, 12, 15),
                "cloud_cover": 85.0,
                "assets": {},
            },
        ]
        inicio = date(2025, 11, 1)
        fim = date(2025, 12, 31)
        res = ndvi_do_piquete(self.coords, inicio, fim, nuvem_max_pct=20)

        self.assertEqual(res.total_cenas_buscadas, 2)
        self.assertEqual(res.total_cenas_utilizaveis, 0)
        self.assertEqual(res.serie, [])
        self.assertEqual(res.maior_vao_dias, (fim - inicio).days)

    @patch("services.ndvi.buscar_cenas_stac")
    def test_erro_stac_propaga_ndvi_indisponivel(self, mock_stac):
        mock_stac.side_effect = NdviIndisponivelError("Fora do ar")
        with self.assertRaises(NdviIndisponivelError):
            ndvi_do_piquete(self.coords, date(2025, 5, 1), date(2025, 5, 31))


class TestSegurancaEIntegridade(unittest.TestCase):
    """Garante que nenhuma credencial ou chave de API foi commitada."""

    def test_sem_chaves_hardcoded(self):
        caminhos = [
            os.path.join(RAIZ, "services", "ndvi.py"),
            os.path.join(RAIZ, "app.py"),
        ]
        padrao = re.compile(
            r"""(?:api_key|API_KEY|token|secret)\s*=\s*"""
            r"""['"][a-zA-Z0-9_\-]{8,}['"]"""
        )
        for c in caminhos:
            with open(c, "r", encoding="utf-8") as f:
                conteudo = f.read()
            self.assertIsNone(
                padrao.search(conteudo),
                f"Possível token/chave hardcoded detectada no arquivo {c}",
            )


class TestUiNdvi(unittest.TestCase):
    """Testa a integração da seção de NDVI com o app Streamlit."""

    def test_aviso_materia_seca_visivel_no_texto(self):
        self.assertIn(
            "NDVI não equivale a matéria seca", app.AVISO_NDVI_MATERIA_SECA
        )

    def test_render_secao_ndvi_sem_poligono_nao_crash(self):
        """Lote sem polígono deve renderizar aviso e não crashar."""
        lote_sem_poligono = {
            "id": "L99",
            "name": "Piquete Sem Perimetro",
            "poligono": None,
            "area_ha": 15.0,
            "total_ua": 0,
            "capacity_ua": 10,
        }
        with patch("streamlit.expander") as mock_expander, \
             patch("streamlit.info") as mock_info, \
             patch("streamlit.caption") as mock_caption:
            mock_expander.return_value.__enter__.return_value = MagicMock()
            app._render_secao_ndvi_lote(lote_sem_poligono)
            mock_info.assert_called_with(app.AVISO_NDVI_MATERIA_SECA)
            mock_caption.assert_called_once()
            self.assertIn("Demarque o perímetro", mock_caption.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
