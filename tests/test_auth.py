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

    def test_legacy_verify(self):
        legacy = hashlib.sha256("velha".encode()).hexdigest()
        self.assertTrue(db._verify_password("velha", legacy))
        self.assertFalse(db._verify_password("outra", legacy))

    def test_is_legacy(self):
        self.assertTrue(db._is_legacy_hash(hashlib.sha256(b"a").hexdigest()))
        self.assertFalse(db._is_legacy_hash(db._hash("a")))


class TestLegacyMigration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        db.DB_PATH = os.path.join(self.tmp, "test.db")
        db.USE_PG = False
        db.init_db()

    def test_migration_on_login(self):
        import sqlite3
        legacy = hashlib.sha256("segredo".encode()).hexdigest()
        con = sqlite3.connect(db.DB_PATH)
        con.execute("INSERT INTO users (username,password_hash,name,role) VALUES(?,?,?,?)",
                    ("legado", legacy, "Legado", "operator"))
        con.commit(); con.close()

        # Login funciona e NÃO expõe o hash
        u = db.verify_login("legado", "segredo")
        self.assertIsNotNone(u)
        self.assertNotIn("password_hash", u)

        # O hash foi migrado para PBKDF2
        con = sqlite3.connect(db.DB_PATH); con.row_factory = sqlite3.Row
        row = con.execute("SELECT password_hash FROM users WHERE username='legado'").fetchone()
        con.close()
        self.assertTrue(row["password_hash"].startswith("pbkdf2_sha256$"))

        # Login continua funcionando após a migração; senha errada é rejeitada
        self.assertIsNotNone(db.verify_login("legado", "segredo"))
        self.assertIsNone(db.verify_login("legado", "errada"))


if __name__ == "__main__":
    unittest.main()
