"""Prova de interface da seção de NDVI por piquete (Spec 0079).

Garante que:
1. A seção "🛰️ NDVI (satélite)" existe para os piquetes na visão geral.
2. Lote sem perímetro exibe o aviso "demarque o perímetro primeiro"
   e não quebra a tela.
3. O aviso permanente "NDVI não equivale a matéria seca" está sempre
   presente e visível.
4. Lote com perímetro permite acionar a consulta e renderiza métricas
   e gráfico sem erro.

⚠️ Não começa com `test_` de propósito — executado por `tests/test_ui.py`.
"""

from datetime import date
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None

POLIGONO_VALIDO = json.dumps({"type": "Polygon", "coordinates": [[
    [-55.9000, -13.3000], [-55.8950, -13.3000],
    [-55.8950, -13.2950], [-55.9000, -13.2950],
    [-55.9000, -13.3000],
]]})


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestUiNdvi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_ndvi.db"))
        db.init_db()
        db.clear_cache()
        cls.lotes = db.get_all_lotes()
        assert len(cls.lotes) >= 2, "seed sem pelo menos 2 lotes"

    def setUp(self):
        for lote in self.lotes:
            db.set_lote_poligono(lote["id"], None)
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_file(
            os.path.join(RAIZ, "app.py"), default_timeout=180
        )
        at.session_state["authenticated"] = True
        at.session_state["user"] = {
            "id": 1, "username": "admin", "name": "Admin", "role": "admin"
        }
        at.session_state["page"] = "lotes"
        at.run()
        self.assertEqual(
            list(at.exception), [],
            f"app levantou exceção: {[e.value for e in at.exception]}"
        )
        return at

    def test_secao_ndvi_existe_e_aviso_materia_seca_sem_poligono(self):
        at = self._tela()
        rotulos = [ex.label for ex in at.expander]
        self.assertTrue(
            any("NDVI" in r for r in rotulos),
            f"nenhum expander de NDVI encontrado: {rotulos}",
        )

        textos_info = [info.value for info in at.info]
        self.assertTrue(
            any("NDVI não equivale a matéria seca" in t for t in textos_info),
            f"aviso de matéria seca não encontrado: {textos_info}",
        )

        textos_caption = [c.value for c in at.caption]
        self.assertTrue(
            any("Demarque o perímetro" in c for c in textos_caption),
            f"aviso de demarcar perímetro não encontrado: {textos_caption}",
        )

    @patch("services.ndvi.buscar_cenas_stac")
    @patch("services.ndvi.calcular_ndvi_cena")
    def test_consulta_ndvi_com_poligono_renderiza_grafico(
        self, mock_calc, mock_stac
    ):
        lid = self.lotes[0]["id"]
        db.set_lote_poligono(lid, POLIGONO_VALIDO)
        db.clear_cache()

        mock_stac.return_value = [
            {
                "scene_id": "S2_TEST_01",
                "date": date(2025, 5, 10),
                "cloud_cover": 10.0,
                "assets": {"red": {}, "nir": {}, "scl": {}},
            },
            {
                "scene_id": "S2_TEST_02",
                "date": date(2025, 5, 25),
                "cloud_cover": 15.0,
                "assets": {"red": {}, "nir": {}, "scl": {}},
            },
        ]
        mock_calc.side_effect = [0.654, 0.712]

        at = self._tela()

        btn_key = f"ndvi_btn_{lid}"
        botoes = [b for b in at.button if b.key == btn_key]
        self.assertEqual(len(botoes), 1, f"botão {btn_key} não encontrado")
        botoes[0].click()
        at.run()

        self.assertEqual(
            list(at.exception), [],
            f"erro ao clicar em consultar: {[e.value for e in at.exception]}"
        )

        valores_metricas = [m.value for m in at.metric]
        self.assertTrue(
            any("0.712" in str(v) for v in valores_metricas),
            f"métrica com valor 0.712 não encontrada: {valores_metricas}",
        )

        textos_info = [info.value for info in at.info]
        self.assertTrue(
            any("NDVI não equivale a matéria seca" in t for t in textos_info),
            "aviso permanente de matéria seca sumiu após consulta",
        )


if __name__ == "__main__":
    unittest.main()
