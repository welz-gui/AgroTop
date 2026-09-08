"""Provas do leitor CAR com uma amostra pública real e persistência."""

import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

import database as db
from repositories import propriedades
from services.importacao_car import (
    area_camada_ha,
    ler_shapefile_car,
    percentual_sobreposicao,
)


RAIZ = Path(__file__).resolve().parents[1]
AMOSTRA = RAIZ / "tests" / "fixtures" / "car_area_imovel_real.zip"


class TestImportacaoCar(unittest.TestCase):
    def test_amostra_real_do_geobases_tem_perimetro_e_reprojeta(self):
        camadas = ler_shapefile_car(AMOSTRA.read_bytes())
        self.assertIn("Área do Imóvel", camadas)
        camada = camadas["Área do Imóvel"][0]
        self.assertAlmostEqual(area_camada_ha(camada), 47.18, places=2)
        self.assertGreater(len(camada.poligonos[0]), 3)
        self.assertTrue(all(-180 <= lon <= 180 and -90 <= lat <= 90
                            for lon, lat in camada.poligonos[0]))

    def test_zip_sem_shapefile_levanta_erro_em_portugues(self):
        with tempfile.TemporaryFile() as arquivo:
            with zipfile.ZipFile(arquivo, "w") as zipado:
                zipado.writestr("leia-me.txt", "sem geometria")
            arquivo.seek(0)
            with self.assertRaisesRegex(ValueError, "Shapefile"):
                ler_shapefile_car(arquivo.read())

    def test_percentual_de_sobreposicao_bate_com_metade(self):
        propriedade = [(-51.23, -30.03), (-51.22, -30.03),
                       (-51.22, -30.02), (-51.23, -30.02)]
        car = [(-51.23, -30.03), (-51.225, -30.03),
               (-51.225, -30.02), (-51.23, -30.02)]
        self.assertAlmostEqual(percentual_sobreposicao(propriedade, [car]), 50.0, delta=0.2)


class TestPersistenciaCar(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(self.pasta, "car.db"))
        db.init_db()
        db.clear_cache()

    def test_tres_campos_voltam_ao_reabrir_propriedade(self):
        propriedade = propriedades.padrao()
        poligono = json.dumps({"type": "Polygon", "coordinates": [[
            [-51.23, -30.03], [-51.22, -30.03], [-51.22, -30.02]
        ]]})
        self.assertTrue(propriedades.atualizar(
            propriedade["id"], car_numero="MT-123", poligono_car=poligono,
            car_area_ha=47.18))
        db.clear_cache()
        salvo = propriedades.get(propriedade["id"])
        self.assertEqual(salvo["car_numero"], "MT-123")
        self.assertEqual(salvo["poligono_car"], poligono)
        self.assertEqual(salvo["car_area_ha"], 47.18)


if __name__ == "__main__":
    unittest.main()
