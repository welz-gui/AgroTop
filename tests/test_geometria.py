import unittest

from pyproj import Transformer
from shapely.geometry import Polygon

from services.geometria import (
    _coordenadas, _crs_utm, area_hectares, centroide, perimetro_metros, validar,
)


class TestCoordenadas(unittest.TestCase):
    def test_converte_para_float(self):
        resultado = _coordenadas([(1, 2), (3, 4)])
        self.assertEqual(resultado, [(1.0, 2.0), (3.0, 4.0)])
        self.assertTrue(isinstance(resultado[0][0], float))

    def test_aceita_strings_e_converte_para_float(self):
        resultado = _coordenadas([("1.5", "-2.5"), ("3.0", "4.0")])
        self.assertEqual(resultado, [(1.5, -2.5), (3.0, 4.0)])

    def test_remove_ultimo_ponto_se_fechado(self):
        fechado = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (1.0, 1.0)]
        esperado = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        self.assertEqual(_coordenadas(fechado), esperado)

    def test_nao_remove_ultimo_ponto_se_aberto(self):
        aberto = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        esperado = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        self.assertEqual(_coordenadas(aberto), esperado)

    def test_aceita_lista_vazia(self):
        self.assertEqual(_coordenadas([]), [])

    def test_aceita_um_ponto(self):
        self.assertEqual(_coordenadas([(1.0, 1.0)]), [(1.0, 1.0)])

class TestGeometriaPiquete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        para_utm = Transformer.from_crs("EPSG:4326", "EPSG:32721", always_xy=True)
        para_gps = Transformer.from_crs("EPSG:32721", "EPSG:4326", always_xy=True)
        cls.centro_esperado = (-55.9, -13.3)
        centro_x, centro_y = para_utm.transform(*cls.centro_esperado)
        cls.quadrado_100m = [
            para_gps.transform(centro_x - 50.0, centro_y - 50.0),
            para_gps.transform(centro_x + 50.0, centro_y - 50.0),
            para_gps.transform(centro_x + 50.0, centro_y + 50.0),
            para_gps.transform(centro_x - 50.0, centro_y + 50.0),
        ]

    def test_quadrado_de_um_hectare_fica_dentro_de_meio_por_cento(self):
        calculada = area_hectares(self.quadrado_100m)

        self.assertAlmostEqual(calculada, 1.0, delta=0.005)

    def test_calculo_ingenuo_em_graus_superestima_area_em_mt(self):
        projetada = area_hectares(self.quadrado_100m)
        area_em_graus = Polygon(self.quadrado_100m).area
        ingenua = area_em_graus * (111_320.0 ** 2) / 10_000.0
        erro_percentual = abs(ingenua - projetada) / projetada * 100.0

        self.assertGreater(erro_percentual, 2.0)

    def test_anel_aberto_e_fechado_dao_o_mesmo_resultado(self):
        fechado = [*self.quadrado_100m, self.quadrado_100m[0]]

        self.assertAlmostEqual(
            area_hectares(self.quadrado_100m), area_hectares(fechado), places=9
        )
        self.assertAlmostEqual(
            perimetro_metros(self.quadrado_100m), perimetro_metros(fechado), places=6
        )

    def test_perimetro_do_quadrado_conhecido(self):
        self.assertAlmostEqual(
            perimetro_metros(self.quadrado_100m), 400.0, delta=2.0
        )

    def test_perimetro_metros_triangulo_conhecido(self):
        para_utm = Transformer.from_crs("EPSG:4326", "EPSG:32721", always_xy=True)
        para_gps = Transformer.from_crs("EPSG:32721", "EPSG:4326", always_xy=True)
        centro_x, centro_y = para_utm.transform(*self.centro_esperado)

        triangulo_30_40_50 = [
            para_gps.transform(centro_x, centro_y),
            para_gps.transform(centro_x + 30.0, centro_y),
            para_gps.transform(centro_x, centro_y + 40.0),
        ]

        self.assertAlmostEqual(
            perimetro_metros(triangulo_30_40_50), 120.0, delta=1.0
        )

    def test_perimetro_metros_rejeita_poligono_invalido(self):
        invalido = [(-55.9, -13.3), (-55.8, -13.3)]

        with self.assertRaisesRegex(ValueError, "O polígono precisa ter pelo menos 3 vértices."):
            perimetro_metros(invalido)

    def test_centroide_volta_em_longitude_latitude(self):
        lon, lat = centroide(self.quadrado_100m)

        self.assertAlmostEqual(lon, self.centro_esperado[0], places=6)
        self.assertAlmostEqual(lat, self.centro_esperado[1], places=6)

    def test_validar_aceita_poligono_valido(self):
        self.assertEqual(validar(self.quadrado_100m), [])

    def test_validar_recusa_menos_de_tres_vertices(self):
        problemas = validar([(-55.9, -13.3), (-55.8, -13.3)])

        self.assertIn("O polígono precisa ter pelo menos 3 vértices.", problemas)

    def test_validar_recusa_coordenada_fora_de_faixa(self):
        problemas = validar([(181.0, -13.3), (-55.8, -13.3), (-55.8, -13.2)])

        self.assertTrue(any("fora da faixa" in problema for problema in problemas))

    def test_validar_recusa_poligono_auto_interceptante_em_portugues(self):
        gravata = [
            (-55.90, -13.30),
            (-55.89, -13.29),
            (-55.90, -13.29),
            (-55.89, -13.30),
        ]

        problemas = validar(gravata)

        self.assertIn("Polígono auto-interceptante.", problemas)

    def test_validar_recusa_area_zero(self):
        colinear = [(-55.90, -13.30), (-55.89, -13.30), (-55.88, -13.30)]

        problemas = validar(colinear)

        self.assertIn("Área do polígono é zero.", problemas)

    def test_crs_utm_zona_extremo_oeste_sul(self):
        crs = _crs_utm(-180.0, -90.0)
        d = crs.to_dict()
        self.assertEqual(d["zone"], 1)
        self.assertIn("south", d)

    def test_crs_utm_zona_extremo_leste_norte(self):
        crs = _crs_utm(180.0, 90.0)
        d = crs.to_dict()
        self.assertEqual(d["zone"], 60)
        self.assertNotIn("south", d)

    def test_crs_utm_zona_meridiano_greenwich_equador(self):
        crs = _crs_utm(0.0, 0.0)
        d = crs.to_dict()
        self.assertEqual(d["zone"], 31)
        self.assertNotIn("south", d)

    def test_crs_utm_zona_exemplo_real(self):
        crs = _crs_utm(-55.9, -13.3)
        d = crs.to_dict()
        self.assertEqual(d["zone"], 21)
        self.assertIn("south", d)


if __name__ == "__main__":
    unittest.main()
