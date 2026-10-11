"""Testes funcionais e estruturais para a página de lotes.

Critérios de aceite:
1. page_lotes mostra as três abas de navegação (Visão Geral, Novo Lote, Transferir).
2. O alerta de sobreposição aparece quando há lotes com polígonos sobrepostos.
"""

import ast
import json
import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None


class TestEstruturalPageLotes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RAIZ, "app.py"), encoding="utf-8") as f:
            cls.codigo = f.read()

    def test_page_lotes_possui_elementos_basicos(self):
        self.assertIn("def page_lotes():", self.codigo)
        self.assertIn("lotes=db.get_all_lotes()", self.codigo)
        self.assertIn("sobrepostos = _sobreposicoes_dos_lotes(lotes)", self.codigo)
        self.assertIn('st.tabs(["📋 Visão Geral","➕ Novo Lote","🔀 Transferir Animais"])', self.codigo)
        self.assertIn("_render_tab_visao_geral(lotes)", self.codigo)
        self.assertIn("_render_tab_novo_lote()", self.codigo)
        self.assertIn("_lotes_transferir_animais(lotes)", self.codigo)


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestFuncionalPageLotes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_lotes.db"))
        db.init_db()
        db.clear_cache()

    def setUp(self):
        db.clear_cache()
        # Remove todos os polígonos para começar limpo
        for lote in db.get_all_lotes():
            db.set_lote_poligono(lote["id"], None)
        db.clear_cache()

    def _app(self, pagina="lotes", **kwargs):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {
            "id": 1,
            "username": "admin",
            "name": "Administrador",
            "role": "admin",
        }
        at.session_state["page"] = pagina
        for k, v in kwargs.items():
            at.session_state[k] = v
        at.run()
        self.assertEqual(list(at.exception), [], f"Exceções: {[e.value for e in at.exception]}")
        return at

    def test_page_lotes_abas_e_titulo(self):
        at = self._app()
        self.assertTrue(any("Lotes / Pastagem" in m.value for m in at.markdown))
        rotulos = [t.label for t in at.tabs]
        self.assertIn("📋 Visão Geral", rotulos)
        self.assertIn("➕ Novo Lote", rotulos)
        self.assertIn("🔀 Transferir Animais", rotulos)

    def test_page_lotes_aviso_sobreposicao(self):
        lotes = db.get_all_lotes()
        self.assertGreaterEqual(len(lotes), 2, "Seed precisa de pelo menos 2 lotes")
        a, b = lotes[0]["id"], lotes[1]["id"]

        # Dois quadrados que se sobrepõem
        q1 = json.dumps({"type": "Polygon", "coordinates": [[
            [-51.2300, -30.0300], [-51.2280, -30.0300],
            [-51.2280, -30.0320], [-51.2300, -30.0320],
            [-51.2300, -30.0300]]]})
        q2 = json.dumps({"type": "Polygon", "coordinates": [[
            [-51.2295, -30.0305], [-51.2275, -30.0305],
            [-51.2275, -30.0325], [-51.2295, -30.0325],
            [-51.2295, -30.0305]]]})

        db.set_lote_poligono(a, q1)
        db.set_lote_poligono(b, q2)
        db.clear_cache()

        at = self._app()
        avisos = [w.value for w in at.warning]
        aviso_sobreposicao = next((w for w in avisos if "Piquetes com perímetro sobreposto" in w), None)
        self.assertIsNotNone(aviso_sobreposicao)
        self.assertIn(str(a), aviso_sobreposicao)
        self.assertIn(str(b), aviso_sobreposicao)


if __name__ == "__main__":
    unittest.main()
