import unittest
from unittest.mock import patch
import pandas as pd
import app

class TestAppExport(unittest.TestCase):
    def test_df_to_xlsx_success(self):
        df = pd.DataFrame({"col1": [1, 2], "col2": ["A", "B"]})
        result = app._df_to_xlsx("Teste", df)
        self.assertIsInstance(result, bytes)
        self.assertTrue(len(result) > 0)
        self.assertTrue(result.startswith(b"PK")) # openpyxl zip magic number

    def test_df_to_xlsx_error_path(self):
        df = pd.DataFrame({"col1": [1, 2]})
        # Mocking pandas.ExcelWriter to raise an exception
        with patch("pandas.ExcelWriter", side_effect=Exception("Simulated error")):
            result = app._df_to_xlsx("Teste Erro", df)
            self.assertEqual(result, b"")

if __name__ == '__main__':
    unittest.main()
