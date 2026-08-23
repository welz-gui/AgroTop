import unittest
from unittest.mock import patch

from services.zootecnia import get_age_display, calculate_gmd_total


class TestZootecniaGetAgeDisplay(unittest.TestCase):
    @patch("services.zootecnia.get_age_months")
    def test_no_birth_date_returns_dash(self, mock_get_age_months):
        mock_get_age_months.return_value = None
        animal = {}
        result = get_age_display(animal)
        self.assertEqual(result, "—")
        mock_get_age_months.assert_called_once_with(None)

    @patch("services.zootecnia.get_age_months")
    def test_years_and_months_display(self, mock_get_age_months):
        mock_get_age_months.return_value = 27  # 2 years and 3 months
        animal = {"birth_date": "2021-01-01"}
        result = get_age_display(animal)
        self.assertEqual(result, "2a 3m")
        mock_get_age_months.assert_called_once_with("2021-01-01")

    @patch("services.zootecnia.get_age_months")
    def test_exactly_one_year(self, mock_get_age_months):
        mock_get_age_months.return_value = 12
        animal = {"birth_date": "2022-01-01"}
        result = get_age_display(animal)
        self.assertEqual(result, "1 ano")

    @patch("services.zootecnia.get_age_months")
    def test_multiple_years(self, mock_get_age_months):
        mock_get_age_months.return_value = 24
        animal = {"birth_date": "2021-01-01"}
        result = get_age_display(animal)
        self.assertEqual(result, "2 anos")

    @patch("services.zootecnia.get_age_months")
    def test_exactly_one_month(self, mock_get_age_months):
        mock_get_age_months.return_value = 1
        animal = {"birth_date": "2023-01-01"}
        result = get_age_display(animal)
        self.assertEqual(result, "1 mes")

    @patch("services.zootecnia.get_age_months")
    def test_multiple_months(self, mock_get_age_months):
        mock_get_age_months.return_value = 5
        animal = {"birth_date": "2023-01-01"}
        result = get_age_display(animal)
        self.assertEqual(result, "5 meses")

    @patch("services.zootecnia.get_age_months")
    def test_zero_months(self, mock_get_age_months):
        mock_get_age_months.return_value = 0
        animal = {"birth_date": "2024-01-01"}
        result = get_age_display(animal)
        self.assertEqual(result, "0 meses")

    @patch("services.zootecnia.get_age_months")
    def test_estimated_age_suffix(self, mock_get_age_months):
        mock_get_age_months.return_value = 24
        animal = {"birth_date": "2021-01-01", "birth_estimated": True}
        result = get_age_display(animal)
        self.assertEqual(result, "2 anos (est.)")

    @patch("services.zootecnia.get_age_months")
    def test_estimated_age_suffix_with_months(self, mock_get_age_months):
        mock_get_age_months.return_value = 15
        animal = {"birth_date": "2022-01-01", "birth_estimated": True}
        result = get_age_display(animal)
        self.assertEqual(result, "1a 3m (est.)")


class TestZootecniaCalculateGMDTotal(unittest.TestCase):
    def test_empty_dict_returns_none(self):
        # Missing entry_date, current_weight, entry_weight causes KeyError
        self.assertIsNone(calculate_gmd_total({}))

    def test_invalid_date_format_returns_none(self):
        # Invalid date format causes ValueError
        animal = {
            "entry_date": "invalid-date",
            "current_weight": 300.0,
            "entry_weight": 200.0
        }
        self.assertIsNone(calculate_gmd_total(animal))

    def test_missing_weight_returns_none(self):
        # Missing current_weight causes KeyError
        animal = {
            "entry_date": "2023-01-01",
            "entry_weight": 200.0
        }
        self.assertIsNone(calculate_gmd_total(animal))

    def test_invalid_type_returns_none(self):
        # Invalid types for weights causes TypeError
        animal = {
            "entry_date": "2023-01-01",
            "current_weight": "300.0",
            "entry_weight": "200.0"
        }
        self.assertIsNone(calculate_gmd_total(animal))

    def test_none_returns_none(self):
        # None passed as animal causes TypeError when trying to index
        self.assertIsNone(calculate_gmd_total(None))
