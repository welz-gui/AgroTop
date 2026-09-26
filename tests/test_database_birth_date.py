import unittest
from datetime import date
from unittest.mock import patch

import database as db

class TestBirthDateFromAge(unittest.TestCase):

    def test_birth_date_from_age_happy_path(self):
        result = db.birth_date_from_age(12, date(2024, 5, 10))
        self.assertEqual(result, "2023-05-15")

    def test_birth_date_from_age_happy_path_no_ref_date(self):
        with patch('database.date') as mock_date:
            mock_date.today.return_value = date(2024, 5, 10)
            mock_date.side_effect = lambda *args: date(*args) if args else mock_date

            result = db.birth_date_from_age(12)
            self.assertEqual(result, "2023-05-15")

    @patch('database.date')
    def test_birth_date_from_age_value_error_fallback(self, mock_date):
        def side_effect(*args):
            if len(args) == 3 and args[2] == 15:
                raise ValueError("Day 15 is out of bounds (simulated)")
            from datetime import date as real_date
            return real_date(*args)

        mock_date.side_effect = side_effect
        mock_date.today.return_value = date(2024, 5, 10)

        result = db.birth_date_from_age(12, date(2024, 5, 10))
        self.assertEqual(result, "2023-05-01")
