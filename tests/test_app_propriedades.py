import unittest
from unittest.mock import patch, MagicMock

import app

class TestAppPropriedades(unittest.TestCase):
    @patch('app.st')
    @patch('app.db')
    def test_page_propriedades_acesso_restrito(self, mock_db, mock_st):
        mock_session = MagicMock()
        mock_session.user = {"role": "operador"}
        mock_st.session_state = mock_session

        app.page_propriedades()

        mock_st.error.assert_called_once_with("🔒 Acesso restrito ao Administrador.")
        mock_st.markdown.assert_not_called()

    @patch('app.st')
    @patch('app.db')
    @patch('app._propriedades_editar')
    @patch('app._propriedade_nova')
    def test_page_propriedades_acesso_admin(self, mock_nova, mock_editar, mock_db, mock_st):
        mock_session = MagicMock()
        mock_session.user = {"role": "admin"}
        mock_st.session_state = mock_session

        mock_db.propriedades.listar.return_value = [{"id": 1, "nome": "Propriedade Teste"}]

        mock_tab1 = MagicMock()
        mock_tab2 = MagicMock()
        mock_st.tabs.return_value = [mock_tab1, mock_tab2]
        mock_tab1.__enter__.return_value = mock_tab1
        mock_tab2.__enter__.return_value = mock_tab2

        app.page_propriedades()

        mock_st.error.assert_not_called()
        mock_st.markdown.assert_called_once_with('<div class="page-title">🏞️ Propriedades</div>', unsafe_allow_html=True)
        mock_db.propriedades.listar.assert_called_once_with(apenas_ativas=False)
        mock_st.tabs.assert_called_once_with(["📋 Cadastradas (1)", "➕ Nova propriedade"])

        mock_editar.assert_called_once_with([{"id": 1, "nome": "Propriedade Teste"}])
        mock_nova.assert_called_once()

if __name__ == '__main__':
    unittest.main()
