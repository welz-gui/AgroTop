import unittest
from unittest.mock import patch, MagicMock

import app

class TestAppRelatorios(unittest.TestCase):
    @patch('app.st')
    @patch('app.db')
    @patch('app._tab_relatorio_inventario')
    @patch('app._tab_relatorio_pesagens')
    @patch('app._tab_relatorio_financeiro')
    @patch('app._tab_relatorio_evidencias')
    def test_page_relatorios(self, mock_tab_evidencias, mock_tab_financeiro, mock_tab_pesagens, mock_tab_inventario, mock_db, mock_st):
        # Mocking the returned animals
        mock_animals = [{"id": 1, "status": "active"}, {"id": 2, "status": "sold"}]
        mock_db.get_all_animals.return_value = mock_animals

        # Simulating the tabs context managers
        mock_rt1 = MagicMock()
        mock_rt2 = MagicMock()
        mock_rt3 = MagicMock()
        mock_rt4 = MagicMock()
        mock_st.tabs.return_value = (mock_rt1, mock_rt2, mock_rt3, mock_rt4)

        # Execute the function
        app.page_relatorios()

        # Verify markdown and tabs calls
        mock_st.markdown.assert_called_with('<div class="page-title">📄 Relatórios e Exportação</div>', unsafe_allow_html=True)
        mock_st.tabs.assert_called_with(["🐄 Inventário", "⚖️ Pesagens", "💰 Financeiro", "📦 Pacote de Evidências"])

        # Verify db call
        mock_db.get_all_animals.assert_called_with(status=None)

        # Verify context manager enters
        mock_rt1.__enter__.assert_called()
        mock_rt2.__enter__.assert_called()
        mock_rt3.__enter__.assert_called()
        mock_rt4.__enter__.assert_called()

        # Verify tab functions were called with correct parameters
        mock_tab_inventario.assert_called_with(mock_animals)
        mock_tab_pesagens.assert_called_with()
        mock_tab_financeiro.assert_called_with(mock_animals)
        mock_tab_evidencias.assert_called_with()

if __name__ == '__main__':
    unittest.main()
