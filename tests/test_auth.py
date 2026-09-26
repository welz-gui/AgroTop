"""Testes de autenticação: hashing PBKDF2 e migração de hashes legados SHA-256."""

import os
import sys
import hashlib
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db  # noqa: E402


class TestPasswordHashing(unittest.TestCase):
    def test_pbkdf2_format(self):
        h = db._hash("senha123")
        self.assertTrue(h.startswith("pbkdf2_sha256$"))
        self.assertEqual(len(h.split("$")), 4)

    def test_roundtrip(self):
        h = db._hash("MinhaSenha!")
        self.assertTrue(db._verify_password("MinhaSenha!", h))
        self.assertFalse(db._verify_password("errada", h))

    def test_salt_aleatorio(self):
        # Dois hashes da mesma senha devem diferir (salt aleatório)
        self.assertNotEqual(db._hash("x"), db._hash("x"))

    def test_is_legacy(self):
        self.assertTrue(db._is_legacy_hash(hashlib.sha256(b"a").hexdigest()))
        self.assertFalse(db._is_legacy_hash(db._hash("a")))


class TestLegacyMigration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Aponta a conexão para um SQLite descartável. Ver repositories/conexao.py:
        # atribuir db.DB_PATH não tem efeito desde que a camada foi separada.
        db.configurar_sqlite(os.path.join(self.tmp, "test.db"))
        db.init_db()

    def test_legacy_hash_rejected_on_login(self):
        import sqlite3
        legacy = hashlib.sha256("segredo".encode()).hexdigest()
        con = sqlite3.connect(db.DB_PATH)
        con.execute("INSERT INTO users (username,password_hash,name,role) VALUES(?,?,?,?)",
                    ("legado", legacy, "Legado", "operator"))
        con.commit(); con.close()

        # Login fails with legacy hash
        u = db.verify_login("legado", "segredo")
        self.assertIsNone(u)


if __name__ == "__main__":
    unittest.main()
