"""Testes para o módulo database.py."""

import unittest
from unittest.mock import patch, MagicMock

import database as db

class TestInitDb(unittest.TestCase):
    def setUp(self):
        # Save the original _INICIALIZADO_EM value to restore after test
        self.original_inicializado_em = db._INICIALIZADO_EM
        # Reset the value before each test
        db._INICIALIZADO_EM = None

    def tearDown(self):
        # Restore the original value
        db._INICIALIZADO_EM = self.original_inicializado_em

    @patch('database._conexao.DATABASE_URL', None)
    @patch('database._conexao.DB_PATH', 'dummy.db')
    @patch('database._conn')
    def test_init_db_guard_skips_when_already_initialized(self, mock_conn):
        """init_db deve pular a inicialização se _INICIALIZADO_EM corresponder ao banco atual."""
        db._INICIALIZADO_EM = 'dummy.db'

        db.init_db()

        mock_conn.assert_not_called()

    @patch('database._conexao.DATABASE_URL', None)
    @patch('database._conexao.DB_PATH', 'dummy.db')
    @patch('database._conn')
    def test_init_db_forcar_bypasses_guard(self, mock_conn):
        """init_db com forcar=True deve ignorar a guarda e rodar a inicialização."""
        db._INICIALIZADO_EM = 'dummy.db'

        # Mocks para as funções internas chamadas dentro do context manager
        mock_conn_ctx = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_conn_ctx

        with patch('database._migrate'), \
             patch('database._seed_users'), \
             patch('database._seed_fornecedores'), \
             patch('database.propriedades._seed_hierarquia', return_value=1), \
             patch('database._seed_lotes'), \
             patch('database._seed_animals'), \
             patch('database._seed_insumos'), \
             patch('database._backfill_uuids'), \
             patch('database._backfill_animal_uuid'), \
             patch('database._backfill_identificadores'), \
             patch('database.propriedades._backfill_property_id'):

            db.init_db(forcar=True)

        mock_conn.assert_called_once()
        self.assertEqual(db._INICIALIZADO_EM, 'dummy.db')

    @patch('database._conexao.DATABASE_URL', None)
    @patch('database._conexao.DB_PATH', 'dummy.db')
    @patch('database._conn')
    def test_init_db_does_not_update_guard_on_failure(self, mock_conn):
        """Se a inicialização falhar (lançar exceção), _INICIALIZADO_EM não deve ser atualizado."""
        db._INICIALIZADO_EM = None

        mock_conn_ctx = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_conn_ctx

        with patch('database._migrate', side_effect=Exception("Simulated failure")):
            with self.assertRaises(Exception):
                db.init_db()

        self.assertIsNone(db._INICIALIZADO_EM)
        mock_conn.assert_called_once()

    @patch('database._conexao.DATABASE_URL', None)
    @patch('database._conexao.DB_PATH', 'dummy.db')
    @patch('database._conexao.USE_PG', False)
    @patch('database._conn')
    def test_init_db_executescript_in_sqlite(self, mock_conn):
        """Em SQLite, deve chamar executescript com _SCHEMA_SQL."""
        db._INICIALIZADO_EM = None

        mock_conn_ctx = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_conn_ctx

        with patch('database._migrate'), \
             patch('database._seed_users'), \
             patch('database._seed_fornecedores'), \
             patch('database.propriedades._seed_hierarquia', return_value=1), \
             patch('database._seed_lotes'), \
             patch('database._seed_animals'), \
             patch('database._seed_insumos'), \
             patch('database._backfill_uuids'), \
             patch('database._backfill_animal_uuid'), \
             patch('database._backfill_identificadores'), \
             patch('database.propriedades._backfill_property_id'):

            db.init_db()

        mock_conn_ctx.executescript.assert_called_once_with(db._SCHEMA_SQL)

    @patch('database._conexao.DATABASE_URL', 'postgres://user:pass@host/db')
    @patch('database._conexao.DB_PATH', 'dummy.db')
    @patch('database._conexao.USE_PG', True)
    @patch('database._conn')
    def test_init_db_skips_executescript_in_postgres(self, mock_conn):
        """Em Postgres, não deve chamar executescript (o schema já vem nas migrations)."""
        db._INICIALIZADO_EM = None

        mock_conn_ctx = MagicMock()
        mock_conn.return_value.__enter__.return_value = mock_conn_ctx

        with patch('database._migrate'), \
             patch('database._seed_users'), \
             patch('database._seed_fornecedores'), \
             patch('database.propriedades._seed_hierarquia', return_value=1), \
             patch('database._seed_lotes'), \
             patch('database._seed_animals'), \
             patch('database._seed_insumos'), \
             patch('database._backfill_uuids'), \
             patch('database._backfill_animal_uuid'), \
             patch('database._backfill_identificadores'), \
             patch('database.propriedades._backfill_property_id'):

            db.init_db()

        mock_conn_ctx.executescript.assert_not_called()
        self.assertEqual(db._INICIALIZADO_EM, 'postgres://user:pass@host/db')


if __name__ == "__main__":
    unittest.main()
