"""Tela de administração: tabelas de histórico avisam que não aceitam exclusão.

Critérios:
1. Em tabela de histórico (ex.: weighings) a edição direta mostra o aviso de que dá
   para corrigir e acrescentar, mas não remover.
2. Em tabela comum (ex.: fornecedores) o aviso não aparece.
"""

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

AVISO = "guarda o histórico dos animais"


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestAdminHistorico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_admin_historico.db"))
        db.init_db()
        db.clear_cache()

    def _tela(self, tabela):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {"id": 1, "username": "admin", "name": "Admin", "role": "admin"}
        at.session_state["page"] = "admin"
        at.session_state["admin_tab_edit"] = tabela
        at.run()
        self.assertEqual(list(at.exception), [])
        return at

    def test_tabela_de_historico_mostra_o_aviso(self):
        at = self._tela("weighings")
        self.assertTrue(any(AVISO in i.value for i in at.info), [i.value for i in at.info])

    def test_tabela_comum_nao_mostra_o_aviso(self):
        at = self._tela("fornecedores")
        self.assertFalse(any(AVISO in i.value for i in at.info))


if __name__ == "__main__":
    unittest.main()
