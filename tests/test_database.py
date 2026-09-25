import unittest
from unittest.mock import patch

import database as db

class TestDatabase(unittest.TestCase):

    @patch('database.get_setting')
    def test_get_gmd_target_happy_path(self, mock_get_setting):
        """Test getting gmd target successfully."""
        mock_get_setting.return_value = "0.75"
        result = db.get_gmd_target()
        self.assertEqual(result, 0.75)
        mock_get_setting.assert_called_once_with("gmd_meta", "0.500")

    @patch('database.get_setting')
    def test_get_gmd_target_value_error(self, mock_get_setting):
        """Test ValueError path where get_setting returns a string that can't be cast to float."""
        mock_get_setting.return_value = "invalid-string"
        result = db.get_gmd_target()
        self.assertEqual(result, 0.5)

    @patch('database.get_setting')
    def test_get_gmd_target_type_error(self, mock_get_setting):
        """Test TypeError path where get_setting returns a type that can't be cast to float like None."""
        mock_get_setting.return_value = None
        result = db.get_gmd_target()
        self.assertEqual(result, 0.5)

if __name__ == '__main__':
    unittest.main()
