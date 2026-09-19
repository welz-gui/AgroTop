import unittest
import os
import sqlite3
import database as db

class TestAdminSecurity(unittest.TestCase):
    def setUp(self):
        # We ensure a clean isolated memory database for these tests
        os.environ["AGROTOP_TESTING"] = "1"
        os.environ["AGROTOP_FORCE_SQLITE"] = "1"
        db.configurar_sqlite(":memory:")

        # We execute the full schema setup.
        # SQLite isolates tables within each connection when using :memory:
        # Let's ensure the connection persists for the test using db._conn
        # Wait, db._conn() provides a fresh connection to :memory: which empties it!
        # In testing, we use db.configurar_sqlite to point to a file to maintain state.
        db.configurar_sqlite("test_admin_security.db")
        with db._conn() as con:
            con.executescript(db._SCHEMA_SQL)
            # Make sure it creates users
            con.execute("INSERT INTO users (username, password_hash, name, role) VALUES ('admin', 'hash', 'Admin', 'admin')")
            self.user_id = con.execute("SELECT id FROM users").fetchone()["id"]

    def tearDown(self):
        if os.path.exists("test_admin_security.db"):
            os.remove("test_admin_security.db")

    def test_injection_in_table_name_rejected(self):
        malicious_table = "users; DROP TABLE users;"
        with self.assertRaises(ValueError) as context:
            db.admin_apply_changes(malicious_table, [], [], [])
        self.assertIn("Tabela não permitida", str(context.exception))
        with db._conn() as con:
            rows = con.execute("SELECT COUNT(*) as count FROM users").fetchone()
            self.assertEqual(rows["count"], 1)

    def test_injection_in_column_name_ignored(self):
        malicious_column = "role = 'admin'; --"
        updates = [{"id": self.user_id, malicious_column: "hacked", "name": "Changed"}]
        res = db.admin_apply_changes("users", updates, [], [])
        self.assertEqual(res["updated"], 1)
        with db._conn() as con:
            user = con.execute("SELECT * FROM users WHERE id=?", (self.user_id,)).fetchone()
            self.assertEqual(user["name"], "Changed")
            self.assertEqual(user["role"], "admin")

    def test_injection_in_value_parameterized(self):
        malicious_value = "Admin' OR 1=1; --"
        updates = [{"id": self.user_id, "name": malicious_value}]
        res = db.admin_apply_changes("users", updates, [], [])
        self.assertEqual(res["updated"], 1)
        with db._conn() as con:
            user = con.execute("SELECT name FROM users WHERE id=?", (self.user_id,)).fetchone()
            self.assertEqual(user["name"], malicious_value)

if __name__ == '__main__':
    unittest.main()
