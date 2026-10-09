"""Testes de interface para a página de calendário sanitário.

Critérios:
1. page_sanitario bloqueia o acesso se não for "admin".
2. page_sanitario renderiza o título e as abas corretas se for "admin".
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


@unittest.skipIf(AppTest is None, "streamlit.testing indisponível")
class TestFuncionalSanitario(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st
        st.cache_data.clear()
        cls.dir = tempfile.mkdtemp()
        db.configurar_sqlite(os.path.join(cls.dir, "ui_sanitario.db"))
        db.init_db()
        db.clear_cache()
        cls.caminho_app = os.path.join(RAIZ, "app.py")

    def _app(self, role="admin", pagina="sanitario"):
        at = AppTest.from_file(self.caminho_app, default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {
            "id": 1 if role == "admin" else 2,
            "username": role,
            "name": "User",
            "role": role,
        }
        at.session_state["page"] = pagina
        at.run()
        return at

    def test_bloqueia_acesso_nao_admin(self):
        """Se o usuário for operador, a tela do calendário sanitário deve ser bloqueada."""
        # The main router intercepts and sends non-admin to 'campo'.
        # However, if we just want to ensure that `page_sanitario` is secure on its own,
        # we can still test the main app. Let's see what happens. If the router intercepts,
        # `page` becomes "campo", and we don't see the title anyway.
        # But wait, `page_sanitario` has explicit:
        # if st.session_state.user["role"] != "admin": st.error("...") ; return
        # The router does: if user["role"] != "admin" and st.session_state.page not in OPERATOR_PAGES: page = "campo"
        # Since "sanitario" is not in OPERATOR_PAGES, the user is redirected to "campo".
        # Let's verify that the user indeed is redirected and does not see the page.

        app = self._app(role="operator", pagina="sanitario")

        # O router do main deve jogar o usuário para 'campo' ou a função bloqueia.
        # Verifica se o título "Calendário Sanitário" NÃO está presente
        titulos_markdown = [md.value for md in app.markdown if "Calendário Sanitário" in md.value]
        self.assertEqual(len(titulos_markdown), 0, "A tela Sanitário não deve ser renderizada para operadores")

        # Pode estar em "campo" agora
        self.assertEqual(app.session_state["page"], "campo")

    def test_acesso_admin_renderiza_tela(self):
        """Se o usuário for admin, a tela do calendário sanitário deve ser renderizada."""
        app = self._app(role="admin", pagina="sanitario")

        # Verifica se o erro de acesso restrito NÃO está presente
        erros = [msg.value for msg in app.error if "Acesso restrito ao Administrador" in msg.value]
        self.assertEqual(len(erros), 0)

        # Verifica se o título da página está presente
        titulos_markdown = [md.value for md in app.markdown if "Calendário Sanitário" in md.value]
        self.assertGreater(len(titulos_markdown), 0, "O título da tela Sanitário não foi encontrado")

        # Verifica as abas (Plano de Vacinação e Protocolos)
        # Em app.tabs temos as abas renderizadas.
        labels = [tab.label for tab in app.tabs]
        self.assertIn("📋 Plano de Vacinação", labels)
        self.assertIn("⚙️ Protocolos", labels)


if __name__ == "__main__":
    unittest.main()
