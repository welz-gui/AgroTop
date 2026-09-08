"""Prova renderizada da seção ambiental da propriedade."""

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


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestUiCar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.pasta = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.pasta, "ui_car.db"))
        db.init_db()
        db.clear_cache()

    def test_secao_e_aviso_de_nao_certificacao_sao_visiveis(self):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin",
                                     "name": "Admin", "role": "admin"}
        at.session_state["page"] = "propriedades"
        at.run()
        self.assertEqual(list(at.exception), [])
        self.assertTrue(any("Situação Ambiental (CAR)" in ex.label for ex in at.expander))
        self.assertIn(
            "não é avaliação de conformidade legal nem certificação oficial",
            " ".join(w.value for w in at.warning),
        )


if __name__ == "__main__":
    unittest.main()
