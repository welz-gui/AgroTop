"""Prova AppTest da consulta IA, executada pelo subprocesso de test_ui."""

import os
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import database as db
from services import assistente_ia as ia

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestUiAssistente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import streamlit as st

        st.cache_data.clear()
        cls.pasta = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.pasta.cleanup)
        db.configurar_sqlite(os.path.join(cls.pasta.name, "assistente.db"))
        db.init_db()
        db.clear_cache()

    def setUp(self):
        # Mesmo se a máquina tiver credencial, esta prova não pode fazer rede.
        self.rede = patch.object(
            ia.requests, "post", side_effect=AssertionError("Rede não autorizada")
        ).start()
        self.contexto = patch.object(
            ia, "montar_contexto", return_value={"rebanho": {"total": 2}}
        ).start()
        self.perguntar = patch.object(ia, "perguntar", return_value="Dois animais.").start()
        self.addCleanup(patch.stopall)

    def tela(self, role="admin", tema="escuro"):
        at = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=180)
        at.session_state["authenticated"] = True
        at.session_state["user"] = {
            "id": 1,
            "username": "teste",
            "name": "Teste",
            "role": role,
            "theme": tema,
        }
        at.session_state["page"] = "assistente"
        at.run()
        self.assertEqual(list(at.exception), [])
        return at

    def test_sem_chave_aviso_visivel_sem_consulta(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            at = self.tela()
        self.assertIn("Recurso não configurado", " ".join(w.value for w in at.info))
        self.assertIn(ia.AVISO_PRIVACIDADE, [w.value for w in at.warning])
        self.assertEqual(len(at.text_area), 0)
        self.contexto.assert_not_called()
        self.perguntar.assert_not_called()
        self.rede.assert_not_called()

    def test_so_consulta_ao_clicar_e_rotulo_ia_nos_dois_temas(self):
        for tema in ("escuro", "claro"):
            with (
                self.subTest(tema=tema),
                patch("ui.tema.TEMA_PADRAO", tema),
                patch.dict(
                    os.environ,
                    {"OPENROUTER_API_KEY": "chave-ficticia", "OPENROUTER_MODEL": "modelo-teste"},
                ),
            ):
                self.perguntar.reset_mock()
                at = self.tela(tema=tema)
                self.assertIn(ia.AVISO_PRIVACIDADE, [w.value for w in at.warning])
                at.text_area(key="assistente_pergunta").set_value("Quantos animais?").run()
                self.perguntar.assert_not_called()
                at.button(key="assistente_enviar").click().run()
                self.assertEqual(list(at.exception), [])
                self.perguntar.assert_called_once_with(
                    "Quantos animais?",
                    {"rebanho": {"total": 2}},
                    api_key="chave-ficticia",
                    modelo="modelo-teste",
                )
                self.assertTrue(any("Resposta gerada por IA" in w.value for w in at.info))
                self.assertIn("Dois animais.", [w.value for w in at.text])
                at.run()
                self.assertEqual(self.perguntar.call_count, 1)
                self.assertNotIn("Dois animais.", [w.value for w in at.text])
        self.rede.assert_not_called()

    def test_erro_amigavel_e_pergunta_vazia(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "chave-ficticia"}):
            at = self.tela()
            at.button(key="assistente_enviar").click().run()
            self.perguntar.assert_not_called()
            self.contexto.assert_not_called()
            self.perguntar.side_effect = ia.AssistenteIndisponivelError(
                "O limite de consultas foi atingido. Tente novamente mais tarde."
            )
            at.text_area(key="assistente_pergunta").set_value("Como está a fazenda?")
            at.button(key="assistente_enviar").click().run()
        self.assertEqual(list(at.exception), [])
        self.assertTrue(any("limite de consultas" in w.value for w in at.error))
        self.assertNotIn("chave-ficticia", str(at))

    def test_operador_nao_tem_menu_nem_acesso_direto(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "chave-ficticia"}):
            at = self.tela(role="operator")
        self.assertEqual(at.session_state["page"], "campo")
        self.assertFalse(any(b.key == "nav_assistente" for b in at.button))
        self.assertEqual(len(at.text_area), 0)
        self.perguntar.assert_not_called()
        self.contexto.assert_not_called()


if __name__ == "__main__":
    unittest.main()
