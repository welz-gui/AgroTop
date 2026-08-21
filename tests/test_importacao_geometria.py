"""Testes unitários para services.importacao_geometria (Spec 0045)."""

import json
import unittest
from services.importacao_geometria import ler_geojson, ler_kml
from services.geometria import validar, area_hectares


class TestImportacaoGeometria(unittest.TestCase):

    def setUp(self):
        # Polígono padrão de teste (quadrado em MT ~100 ha)
        self.coords_padrao = [
            (-55.5000, -12.5000),
            (-55.4900, -12.5000),
            (-55.4900, -12.4900),
            (-55.5000, -12.4900),
            (-55.5000, -12.5000),
        ]

    def test_criterio_1_geojson_polygon_nu(self):
        """Critério 1: GeoJSON com geometria Polygon 'nua' é lido corretamente."""
        conteudo = json.dumps({
            "type": "Polygon",
            "coordinates": [self.coords_padrao],
        })
        vertices = ler_geojson(conteudo)
        self.assertEqual(len(vertices), 5)
        self.assertEqual(vertices, self.coords_padrao)

    def test_criterio_2_geojson_feature(self):
        """Critério 2: GeoJSON Feature envolvendo Polygon é lido corretamente."""
        conteudo = json.dumps({
            "type": "Feature",
            "properties": {"nome": "Piquete 01", "area_declarada": 120.5},
            "geometry": {
                "type": "Polygon",
                "coordinates": [self.coords_padrao],
            },
        })
        vertices = ler_geojson(conteudo)
        self.assertEqual(vertices, self.coords_padrao)

    def test_criterio_3_geojson_feature_collection(self):
        """Critério 3: GeoJSON FeatureCollection é lido a partir do primeiro Feature."""
        conteudo = json.dumps({
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": 1},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [self.coords_padrao],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"id": 2},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]],
                    },
                },
            ],
        })
        vertices = ler_geojson(conteudo)
        self.assertEqual(vertices, self.coords_padrao)

    def test_criterio_4_geojson_multipolygon_recusa_com_value_error(self):
        """Critério 4: GeoJSON MultiPolygon levanta ValueError explicitamente."""
        conteudo = json.dumps({
            "type": "MultiPolygon",
            "coordinates": [
                [self.coords_padrao],
                [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            ],
        })
        with self.assertRaises(ValueError) as ctx:
            ler_geojson(conteudo)
        self.assertIn("MultiPolygon", str(ctx.exception))
        self.assertIn("não é suportado", str(ctx.exception))

    def test_criterio_5_kml_com_outer_boundary_e_altitude(self):
        """Critério 5: KML padrão com outerBoundaryIs/LinearRing/coordinates e altitude ignorada."""
        kml_texto = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Piquete Sede</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -55.5000,-12.5000,320.0
              -55.4900,-12.5000,325.5
              -55.4900,-12.4900,322.1
              -55.5000,-12.4900,318.0
              -55.5000,-12.5000,320.0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""
        vertices = ler_kml(kml_texto)
        self.assertEqual(len(vertices), 5)
        self.assertEqual(vertices, self.coords_padrao)

    def test_criterio_6_conteudos_invalidos_levantam_value_error(self):
        """Critério 6: Texto não JSON/XML ou malformado levanta ValueError com mensagem em português."""
        # Não JSON
        with self.assertRaises(ValueError) as ctx_json:
            ler_geojson("texto qualquer que nao e json")
        self.assertIn("JSON", str(ctx_json.exception))

        # JSON vazio / tipo errado
        with self.assertRaises(ValueError):
            ler_geojson("")
        with self.assertRaises(ValueError):
            ler_geojson('{"type": "Point", "coordinates": [1, 2]}')
        with self.assertRaises(ValueError):
            ler_geojson('{"type": "Polygon", "coordinates": []}')

        # Não XML
        with self.assertRaises(ValueError) as ctx_xml:
            ler_kml("isto nao e um xml")
        self.assertIn("XML", str(ctx_xml.exception))

        # XML sem Polygon
        with self.assertRaises(ValueError) as ctx_no_poly:
            ler_kml("<kml><Document><name>Teste</name></Document></kml>")
        self.assertIn("Polygon", str(ctx_no_poly.exception))

        # KML com coordenadas malformadas
        kml_malformado = """<kml><Polygon><outerBoundaryIs><LinearRing><coordinates>
            coordenada_invalida_sem_virgula
        </coordinates></LinearRing></outerBoundaryIs></Polygon></kml>"""
        with self.assertRaises(ValueError):
            ler_kml(kml_malformado)

    def test_criterio_7_integra_com_geometria_validar(self):
        """Critério 7: Vértices de GeoJSON e KML são consumidos direto por geometria.validar() e area_hectares()."""
        geojson_str = json.dumps({"type": "Polygon", "coordinates": [self.coords_padrao]})
        kml_str = """<kml><Polygon><outerBoundaryIs><LinearRing><coordinates>
          -55.5000,-12.5000,0 -55.4900,-12.5000,0 -55.4900,-12.4900,0 -55.5000,-12.4900,0 -55.5000,-12.5000,0
        </coordinates></LinearRing></outerBoundaryIs></Polygon></kml>"""

        v_geojson = ler_geojson(geojson_str)
        v_kml = ler_kml(kml_str)

        self.assertEqual(validar(v_geojson), [])
        self.assertEqual(validar(v_kml), [])

        area_g = area_hectares(v_geojson)
        area_k = area_hectares(v_kml)
        self.assertGreater(area_g, 0.0)
        self.assertAlmostEqual(area_g, area_k, places=2)


if __name__ == "__main__":
    unittest.main()
