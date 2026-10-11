import unittest
from unittest.mock import patch, MagicMock

import app

class TestAppDashboard(unittest.TestCase):

    @patch('app.db')
    @patch('app.st')
    def test_page_dashboard_sem_animais(self, mock_st, mock_db):
        mock_db.get_rebanho_stats.return_value = MagicMock()
        mock_db.get_all_animals.return_value = []
        mock_db.get_alert_animals.return_value = MagicMock()

        app.page_dashboard()

        mock_st.markdown.assert_called_once_with('<div class="page-title">📊 Dashboard — Visão Geral</div>', unsafe_allow_html=True)
        mock_st.info.assert_called_once_with("Nenhum animal cadastrado. Use **Cadastrar Animal** para começar.")

    @patch('app.db')
    @patch('app.st')
    @patch('app._dash_kpis')
    @patch('app._dash_alerts')
    @patch('app._dash_chart_evolucao_peso')
    @patch('app._dash_chart_por_raca')
    @patch('app._dash_chart_gmd')
    @patch('app._dash_summary_table')
    @patch('app._dash_conformidade')
    @patch('app._dash_completude')
    def test_page_dashboard_com_animais(self, mock_completude, mock_conformidade, mock_summary,
                                        mock_gmd, mock_raca, mock_evolucao, mock_alerts, mock_kpis,
                                        mock_st, mock_db):

        mock_stats = MagicMock()
        mock_animals = [MagicMock()]
        mock_alertas = MagicMock()

        mock_db.get_rebanho_stats.return_value = mock_stats
        mock_db.get_all_animals.return_value = mock_animals
        mock_db.get_alert_animals.return_value = mock_alertas

        mock_col_main = MagicMock()
        mock_col_side = MagicMock()
        mock_st.columns.return_value = [mock_col_main, mock_col_side]

        app.page_dashboard()

        # Check st.markdown was called twice (title and separator)
        self.assertEqual(mock_st.markdown.call_count, 2)
        mock_st.markdown.assert_any_call('<div class="page-title">📊 Dashboard — Visão Geral</div>', unsafe_allow_html=True)
        mock_st.markdown.assert_any_call("---")

        mock_kpis.assert_called_once_with(mock_stats, mock_animals)
        mock_alerts.assert_called_once_with(mock_alertas)

        mock_st.columns.assert_called_once_with([3, 2])

        mock_evolucao.assert_called_once()
        mock_raca.assert_called_once_with(mock_animals)
        mock_gmd.assert_called_once_with(mock_animals)

        mock_summary.assert_called_once_with(mock_animals)
        mock_conformidade.assert_called_once()
        mock_completude.assert_called_once()

if __name__ == '__main__':
    unittest.main()
