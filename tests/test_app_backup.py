import unittest
from unittest.mock import patch
import pandas as pd
import io

import app

class TestAppBackup(unittest.TestCase):
    @patch('app.db')
    def test_backup_xlsx_success(self, mock_db):
        mock_db.ADMIN_TABLES = ["tabela_1", "tabela_2"]
        def admin_get_rows_side_effect(t):
            if t == "tabela_1":
                return [{"col1": "A", "col2": "B"}]
            return []
        mock_db.admin_get_rows.side_effect = admin_get_rows_side_effect

        res = app._backup_xlsx()

        self.assertIsInstance(res, bytes)
        xls = pd.ExcelFile(io.BytesIO(res), engine="openpyxl")
        self.assertIn("tabela_1", xls.sheet_names)
        self.assertIn("tabela_2", xls.sheet_names)

    @patch('app.db')
    def test_backup_xlsx_error_path(self, mock_db):
        mock_db.ADMIN_TABLES = ["tabela_erro"]
        def admin_get_rows_side_effect(t):
            raise Exception("Simulated DB Error")
        mock_db.admin_get_rows.side_effect = admin_get_rows_side_effect

        res = app._backup_xlsx()

        self.assertIsInstance(res, bytes)
        xls = pd.ExcelFile(io.BytesIO(res), engine="openpyxl")
        self.assertIn("tabela_erro", xls.sheet_names)
        df_erro = pd.read_excel(xls, "tabela_erro", engine="openpyxl")
        self.assertEqual(df_erro.iloc[0]["erro"], "falha ao ler tabela_erro")

if __name__ == '__main__':
    unittest.main()
