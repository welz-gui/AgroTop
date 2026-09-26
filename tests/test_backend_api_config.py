import os
import unittest
from unittest.mock import patch

from backend_api.config import get_secret_key


class TestBackendApiConfig(unittest.TestCase):

    @patch.dict(os.environ, {"AGROTOP_API_SECRET": "a" * 32})
    def test_get_secret_key_success(self):
        """Testa se a chave secreta é retornada com sucesso quando tem 32+ caracteres."""
        self.assertEqual(get_secret_key(), "a" * 32)

    @patch.dict(os.environ, {}, clear=True)
    def test_get_secret_key_missing(self):
        """Testa se um erro é lançado quando a variável de ambiente não está definida."""
        with self.assertRaisesRegex(RuntimeError, "pelo menos 32 caracteres"):
            get_secret_key()

    @patch.dict(os.environ, {"AGROTOP_API_SECRET": "a" * 31})
    def test_get_secret_key_too_short(self):
        """Testa se um erro é lançado quando a chave tem menos de 32 caracteres."""
        with self.assertRaisesRegex(RuntimeError, "pelo menos 32 caracteres"):
            get_secret_key()

    @patch.dict(os.environ, {"AGROTOP_API_SECRET": " " * 10 + "a" * 31 + " " * 10})
    def test_get_secret_key_whitespace_stripped(self):
        """Testa se espaços em branco são removidos e a chave é validada corretamente."""
        with self.assertRaisesRegex(RuntimeError, "pelo menos 32 caracteres"):
            get_secret_key()

    @patch.dict(os.environ, {"AGROTOP_API_SECRET": " " * 10 + "a" * 32 + " " * 10})
    def test_get_secret_key_whitespace_stripped_success(self):
        """Testa se espaços em branco são removidos e uma chave de 32 caracteres é aceita."""
        self.assertEqual(get_secret_key(), "a" * 32)
