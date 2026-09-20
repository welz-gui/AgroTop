import unittest
from unittest.mock import patch, MagicMock

import app

class TestAppValidacao(unittest.TestCase):
    @patch('app.validar_animal')
    @patch('app.st')
    @patch('app.db')
    def test_consistencia_ignora_codigos_pendentes(self, mock_db, mock_st, mock_validar):
        # We want to ensure that if `validar_animal` returns problems in _CODIGOS_AGUARDANDO_SCHEMA,
        # they are filtered out in app.py

        # mock returned problems
        mock_validar.return_value = [
            {"codigo": "animal_sem_origem", "gravidade": "alerta", "mensagem": "test 1"},
            {"codigo": "nascimento_sem_mae", "gravidade": "alerta", "mensagem": "test 2"},
            {"codigo": "outro_problema_grave", "gravidade": "bloqueio", "mensagem": "test 3"},
        ]

        mock_db.identificadores.get_identificadores.return_value = []
        mock_db.get_deaths.return_value = []

        mock_expander = MagicMock()
        mock_st.expander.return_value.__enter__.return_value = mock_expander

        animal = {"id": "123", "uuid": "abc"}
        movs = []

        app._consistencia_regulatoria(animal, movs)

        # Expand should be called because there's 'outro_problema_grave'
        self.assertTrue(mock_st.expander.called)

        # check that markdown was called exactly once for the 'outro_problema_grave'
        # and not for the pending schema codes
        mock_st.markdown.assert_called_once_with("🔴 **Bloqueio** — test 3")

    @patch('app.validar_animal')
    @patch('app.st')
    @patch('app.db')
    def test_consistencia_sem_problemas(self, mock_db, mock_st, mock_validar):
        # Only ignored problems
        mock_validar.return_value = [
            {"codigo": "animal_sem_origem", "gravidade": "alerta", "mensagem": "test 1"},
        ]

        mock_db.identificadores.get_identificadores.return_value = []
        mock_db.get_deaths.return_value = []

        animal = {"id": "123", "uuid": "abc"}
        movs = []

        app._consistencia_regulatoria(animal, movs)

        # expander should not be called because the only problem was filtered out
        mock_st.expander.assert_not_called()

if __name__ == '__main__':
    unittest.main()
