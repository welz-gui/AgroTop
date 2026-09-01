import unittest
import hashlib
from unittest.mock import patch

from services.seguranca import _hash, _is_legacy_hash, _verify_password, _PBKDF2_ITERATIONS

class TestSeguranca(unittest.TestCase):

    def test_hash_format(self):
        pwd = "minhasenha_secreta"
        hashed = _hash(pwd)

        self.assertTrue(hashed.startswith(f"pbkdf2_sha256${_PBKDF2_ITERATIONS}$"))
        parts = hashed.split("$")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "pbkdf2_sha256")
        self.assertEqual(parts[1], str(_PBKDF2_ITERATIONS))

        # Verify hex format
        bytes.fromhex(parts[2])
        bytes.fromhex(parts[3])

    @patch('secrets.token_bytes')
    def test_hash_deterministic(self, mock_token_bytes):
        # Setup mock to return a known salt (16 bytes as requested in code)
        mock_token_bytes.return_value = b'test_salt_123456'

        pwd = "minhasenha_secreta"
        hashed1 = _hash(pwd)
        hashed2 = _hash(pwd)

        self.assertEqual(hashed1, hashed2)

    def test_is_legacy_hash(self):
        self.assertTrue(_is_legacy_hash(None))
        self.assertTrue(_is_legacy_hash(""))
        self.assertTrue(_is_legacy_hash("some_random_string"))
        self.assertTrue(_is_legacy_hash(hashlib.sha256(b"teste").hexdigest()))

        self.assertFalse(_is_legacy_hash("pbkdf2_sha256$260000$salt$hash"))

    def test_verify_password_pbkdf2(self):
        pwd = "minha_senha"
        hashed = _hash(pwd)

        self.assertTrue(_verify_password(pwd, hashed))
        self.assertFalse(_verify_password("senha_errada", hashed))

    def test_verify_password_legacy(self):
        pwd = "minha_senha"
        legacy_hashed = hashlib.sha256(pwd.encode()).hexdigest()

        self.assertTrue(_verify_password(pwd, legacy_hashed))
        self.assertFalse(_verify_password("senha_errada", legacy_hashed))

    def test_verify_password_empty(self):
        self.assertFalse(_verify_password("senha", None))
        self.assertFalse(_verify_password("senha", ""))

    def test_verify_password_malformed_pbkdf2(self):
        # missing dk_hex (ValueError from split)
        self.assertFalse(_verify_password("senha", "pbkdf2_sha256$260000$salt_hex"))

        # invalid iters (ValueError from int)
        self.assertFalse(_verify_password("senha", "pbkdf2_sha256$abc$salt_hex$dk_hex"))

        # invalid hex (ValueError from bytes.fromhex)
        self.assertFalse(_verify_password("senha", "pbkdf2_sha256$260000$not_hex$dk_hex"))

        # invalid hex for dk_hex (will just return false on compare)
        self.assertFalse(_verify_password("senha", "pbkdf2_sha256$260000$aabb$not_hex"))

if __name__ == '__main__':
    unittest.main()
