import os
import unittest
from unittest.mock import patch, MagicMock

import app
from services import assistente_ia


class TestAppPageAssistente(unittest.TestCase):
    @patch("app.st")
    def test_page_assistente_restrito_admin(self, mock_st):
        mock_st.session_state = MagicMock()
        mock_st.session_state.user = {"role": "operator"}
        app.page_assistente()
        mock_st.error.assert_called_once_with("🔒 Acesso restrito ao Administrador.")

    @patch("app.st")
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": ""})
    def test_page_assistente_sem_chave(self, mock_st):
        mock_st.session_state = MagicMock()
        mock_st.session_state.user = {"role": "admin"}
        app.page_assistente()
        mock_st.info.assert_called_once_with(
            "Recurso não configurado. Solicite a configuração ao administrador."
        )

    @patch("app.st")
    @patch.dict(
        os.environ,
        {"OPENROUTER_API_KEY": "valid_key", "OPENROUTER_MODEL": "test-model"},
    )
    def test_page_assistente_pergunta_vazia(self, mock_st):
        mock_st.session_state = MagicMock()
        mock_st.session_state.user = {"role": "admin"}
        mock_st.text_area.return_value = "   "
        mock_st.button.return_value = True
        app.page_assistente()
        mock_st.info.assert_called_once_with("Digite uma pergunta antes de enviar.")

    @patch("app.st")
    @patch("app.assistente_ia")
    @patch.dict(
        os.environ,
        {"OPENROUTER_API_KEY": "valid_key", "OPENROUTER_MODEL": "test-model"},
    )
    def test_page_assistente_sucesso(self, mock_ia, mock_st):
        mock_st.session_state = MagicMock()
        mock_st.session_state.user = {"role": "admin"}
        mock_st.text_area.return_value = "Como está a fazenda?"
        mock_st.button.return_value = True

        mock_contexto = {"rebanho": {"total": 100}}
        mock_ia.montar_contexto.return_value = mock_contexto
        mock_ia.perguntar.return_value = "A fazenda está bem."

        mock_spinner = MagicMock()
        mock_st.spinner.return_value.__enter__.return_value = mock_spinner

        app.page_assistente()

        mock_ia.montar_contexto.assert_called_once()
        mock_ia.perguntar.assert_called_once_with(
            "Como está a fazenda?",
            mock_contexto,
            api_key="valid_key",
            modelo="test-model",
        )
        mock_st.info.assert_called_once_with(
            "🤖 Resposta gerada por IA — confira os dados antes de decidir."
        )
        mock_st.text.assert_called_once_with("A fazenda está bem.")

    @patch("app.st")
    @patch("app.assistente_ia")
    @patch.dict(
        os.environ,
        {"OPENROUTER_API_KEY": "valid_key", "OPENROUTER_MODEL": "test-model"},
    )
    def test_page_assistente_erro_indisponivel(self, mock_ia, mock_st):
        mock_st.session_state = MagicMock()
        mock_st.session_state.user = {"role": "admin"}
        mock_st.text_area.return_value = "Como está a fazenda?"
        mock_st.button.return_value = True

        mock_ia.montar_contexto.return_value = {}
        mock_ia.AssistenteIndisponivelError = assistente_ia.AssistenteIndisponivelError
        mock_ia.perguntar.side_effect = assistente_ia.AssistenteIndisponivelError(
            "Falha na API"
        )

        mock_spinner = MagicMock()
        mock_st.spinner.return_value.__enter__.return_value = mock_spinner

        app.page_assistente()

        mock_st.error.assert_called_once_with("Falha na API")
        mock_st.text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
