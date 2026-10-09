import os
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import database as db  # noqa: E402

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover
    AppTest = None

def _run_page_cadastrar():
    import app
    app.page_cadastrar()

@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestTelaCadastrar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_cadastrar.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self):
        at = AppTest.from_function(_run_page_cadastrar)
        at.run()
        return at

    def test_abas_nascimento_e_comprado_presentes(self):
        """As abas de nascimento e compra devem existir na tela."""
        at = self._tela()
        self.assertTrue(at.tabs, "Nenhuma tab na tela de cadastro")
        self.assertEqual(len(at.tabs), 2, "A tela deve ter duas abas")
        self.assertIn("Comprado / Recebido", at.tabs[0].label)
        self.assertIn("Nascimento na fazenda", at.tabs[1].label)

    def test_campos_obrigatorios_comprado(self):
        """Verifica se os campos básicos da aba 'Comprado' existem."""
        at = self._tela()
        tab_compra = at.tabs[0]
        self.assertTrue(len(tab_compra.text_input) > 0, "Falta input de texto na aba Comprado")
        self.assertTrue(len(tab_compra.selectbox) > 0, "Falta selectbox na aba Comprado")
        self.assertTrue(len(tab_compra.radio) > 0, "Falta radio na aba Comprado")
        self.assertTrue(len(tab_compra.date_input) > 0, "Falta input de data na aba Comprado")
        self.assertTrue(len(tab_compra.number_input) > 0, "Falta input de número na aba Comprado")

    def test_campos_obrigatorios_nascimento(self):
        """Verifica se os campos básicos da aba 'Nascimento' existem."""
        at = self._tela()
        tab_nasc = at.tabs[1]
        self.assertTrue(len(tab_nasc.selectbox) > 0, "Falta selectbox (Mãe, Raça) na aba Nascimento")
        self.assertTrue(len(tab_nasc.number_input) > 0, "Falta input de número (Quantidade de crias) na aba Nascimento")
        self.assertTrue(len(tab_nasc.date_input) > 0, "Falta input de data na aba Nascimento")

if __name__ == "__main__":
    unittest.main()
