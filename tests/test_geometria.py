import unittest
import pyproj
from shapely.geometry import Polygon
from shapely.ops import transform

from services.geometria import area_hectares, centroide, perimetro_metros, validar


class TestGeometriaPiquetes(unittest.TestCase):
    def setUp(self):
        # Quadrado de 1000m x 1000m = 100 ha na Zona UTM 21S (Mato Grosso)
        # Coordenadas UTM 21S (EPSG:32721):
        utm_square = [
            (619000.0, 8529000.0),
            (620000.0, 8529000.0),
            (620000.0, 8530000.0),
            (619000.0, 8530000.0),
        ]
        to_wgs = pyproj.Transformer.from_crs(
            "EPSG:32721", "EPSG:4326", always_xy=True
        ).transform
        poly_wgs = transform(to_wgs, Polygon(utm_square))
        self.poligono_mt_100ha = list(poly_wgs.exterior.coords)[
            :4
        ]  # 4 pontos abertos

    def test_quadrado_conhecido_mt_dentro_tolerancia_05_porcento(self):
        area_calc = area_hectares(self.poligono_mt_100ha)
        area_esperada = 100.0  # 100 ha
        erro_relativo = abs(area_calc - area_esperada) / area_esperada
        self.assertLess(erro_relativo, 0.005)  # Dentro de 0,5 %

    def test_demonstrar_diferenca_contra_calculo_ingenuo(self):
        # Cálculo projetado correto
        area_correta = area_hectares(self.poligono_mt_100ha)

        # Cálculo ingênuo assumindo 1° = 111.320 m fixo em ambas dimensões
        lons = [p[0] for p in self.poligono_mt_100ha]
        lats = [p[1] for p in self.poligono_mt_100ha]
        delta_lon = max(lons) - min(lons)
        delta_lat = max(lats) - min(lats)
        area_ingenua = (delta_lon * 111320.0) * (delta_lat * 111320.0) / 10000.0

        erro_porcento = abs(area_ingenua - area_correta) / area_correta * 100.0
        # O erro ingênuo em MT é de aproximadamente 4,3% (muito acima dos 0.5% aceitáveis)
        self.assertGreater(erro_porcento, 3.5)

    def test_anel_aberto_e_fechado_dao_mesmo_resultado(self):
        anel_aberto = self.poligono_mt_100ha
        anel_fechado = self.poligono_mt_100ha + [self.poligono_mt_100ha[0]]

        self.assertAlmostEqual(
            area_hectares(anel_aberto), area_hectares(anel_fechado), places=5
        )
        self.assertAlmostEqual(
            perimetro_metros(anel_aberto),
            perimetro_metros(anel_fechado),
            places=2,
        )
        c1 = centroide(anel_aberto)
        c2 = centroide(anel_fechado)
        self.assertAlmostEqual(c1[0], c2[0], places=6)
        self.assertAlmostEqual(c1[1], c2[1], places=6)

    def test_perimetro_metros_quadrado_100ha(self):
        # Quadrado 1000m x 1000m -> Perímetro esperado ≈ 4000m
        perim = perimetro_metros(self.poligono_mt_100ha)
        self.assertAlmostEqual(perim, 4000.0, delta=20.0)

    def test_centroide_posicao(self):
        c = centroide(self.poligono_mt_100ha)
        lons = [p[0] for p in self.poligono_mt_100ha]
        lats = [p[1] for p in self.poligono_mt_100ha]
        self.assertGreater(c[0], min(lons))
        self.assertLess(c[0], max(lons))
        self.assertGreater(c[1], min(lats))
        self.assertLess(c[1], max(lats))

    def test_validar_poligono_valido(self):
        self.assertEqual(validar(self.poligono_mt_100ha), [])

    def test_validar_poucos_vertices(self):
        erros = validar([(-55.9, -13.3), (-55.8, -13.3)])
        self.assertTrue(any("pelo menos 3 vértices" in e for e in erros))

    def test_validar_coordenadas_fora_de_faixa(self):
        erros = validar([(-200.0, -13.3), (-55.8, -13.3), (-55.8, -13.2)])
        self.assertTrue(any("faixa válida" in e for e in erros))

    def test_validar_auto_interceptante(self):
        # Ampulheta (laço cruzado): (0,0), (1,1), (0,1), (1,0)
        laço = [(0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0)]
        erros = validar(laço)
        self.assertTrue(any("auto-interceptante" in e for e in erros))

    def test_validar_area_zero(self):
        # Vértices colineares
        colinear = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]
        erros = validar(colinear)
        self.assertTrue(any("área zero" in e or "inválida" in e for e in erros))


if __name__ == "__main__":
    unittest.main()
