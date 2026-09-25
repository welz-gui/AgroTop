from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

import app

class TestAppLogin(unittest.TestCase):
    @patch('app.st')
    @patch('app.db')
    @patch('app._cookie_manager')
    def test_login_sucesso_admin(self, mock_cm, mock_db, mock_st):
        mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_st.text_input.side_effect = ["admin", "senha123"]
        mock_st.checkbox.return_value = False
        mock_st.form_submit_button.return_value = True

        mock_db.verify_login.return_value = {"id": 1, "role": "admin"}
        mock_st.session_state = MagicMock()
        mock_st.session_state.authenticated = False

        mock_form = MagicMock()
        mock_st.form.return_value.__enter__.return_value = mock_form

        app.page_login()

        self.assertTrue(mock_st.session_state.authenticated)
        self.assertEqual(mock_st.session_state.user, {"id": 1, "role": "admin"})
        self.assertEqual(mock_st.session_state.page, "dashboard")
        mock_st.rerun.assert_called_once()
        mock_cm.assert_not_called()

    @patch('app.st')
    @patch('app.db')
    @patch('app._cookie_manager')
    def test_login_sucesso_campo(self, mock_cm, mock_db, mock_st):
        mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_st.text_input.side_effect = ["operador", "senha123"]
        mock_st.checkbox.return_value = False
        mock_st.form_submit_button.return_value = True

        mock_db.verify_login.return_value = {"id": 2, "role": "operator"}
        mock_st.session_state = MagicMock()
        mock_st.session_state.authenticated = False

        mock_form = MagicMock()
        mock_st.form.return_value.__enter__.return_value = mock_form

        app.page_login()

        self.assertTrue(mock_st.session_state.authenticated)
        self.assertEqual(mock_st.session_state.user, {"id": 2, "role": "operator"})
        self.assertEqual(mock_st.session_state.page, "campo")
        mock_st.rerun.assert_called_once()

    @patch('app.st')
    @patch('app.db')
    def test_login_falha(self, mock_db, mock_st):
        mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_st.text_input.side_effect = ["admin", "errada"]
        mock_st.checkbox.return_value = False
        mock_st.form_submit_button.return_value = True

        mock_db.verify_login.return_value = None

        mock_form = MagicMock()
        mock_st.form.return_value.__enter__.return_value = mock_form

        app.page_login()

        mock_st.error.assert_called_once_with("Usuário ou senha inválidos.")
        mock_st.rerun.assert_not_called()

    @patch('app.st')
    @patch('app.db')
    @patch('app._cookie_manager')
    def test_login_lembrar_me(self, mock_cm_func, mock_db, mock_st):
        mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_st.text_input.side_effect = ["  admin  ", "senha123"]
        mock_st.checkbox.return_value = True
        mock_st.form_submit_button.return_value = True

        mock_db.verify_login.return_value = {"id": 1, "role": "admin"}
        mock_db.create_session.return_value = "token_gerado"

        mock_cm = MagicMock()
        mock_cm_func.return_value = mock_cm

        mock_st.session_state = MagicMock()
        mock_form = MagicMock()
        mock_st.form.return_value.__enter__.return_value = mock_form

        with patch('time.sleep'):
            app.page_login()

        mock_db.verify_login.assert_called_once_with("admin", "senha123")
        mock_db.create_session.assert_called_once_with(1)
        mock_cm.set.assert_called_once()
        self.assertEqual(mock_cm.set.call_args[0][0], app._COOKIE_NAME)
        self.assertEqual(mock_cm.set.call_args[0][1], "token_gerado")

    @patch('app.st')
    @patch('app.db')
    @patch('app._cookie_manager')
    def test_login_lembrar_me_exception(self, mock_cm_func, mock_db, mock_st):
        mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_st.text_input.side_effect = ["admin", "senha123"]
        mock_st.checkbox.return_value = True
        mock_st.form_submit_button.return_value = True

        mock_db.verify_login.return_value = {"id": 1, "role": "admin"}
        mock_db.create_session.return_value = "token_gerado"

        mock_cm = MagicMock()
        mock_cm.set.side_effect = Exception("Erro ao setar cookie")
        mock_cm_func.return_value = mock_cm

        mock_st.session_state = MagicMock()
        mock_form = MagicMock()
        mock_st.form.return_value.__enter__.return_value = mock_form

        app.page_login()
        mock_st.rerun.assert_called_once()

if __name__ == '__main__':
    unittest.main()
