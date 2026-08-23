import unittest
from unittest.mock import patch

from datetime import date

from services.zootecnia import get_age_display, get_age_months


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


class TestZootecniaGetAgeMonths(unittest.TestCase):
    def test_no_birth_date_returns_none(self):
        self.assertIsNone(get_age_months(None))
        self.assertIsNone(get_age_months(""))

    def test_invalid_date_format_returns_none(self):
        self.assertIsNone(get_age_months("invalid-date"))
        self.assertIsNone(get_age_months("01/01/2021"))
        self.assertIsNone(get_age_months("2021-13-45"))

    @patch("services.zootecnia.date")
    def test_age_months_calculation(self, mock_date):
        # Set today's date to a fixed value for deterministic testing
        mock_date.today.return_value = date(2023, 4, 15)
        # Mock side_effect for datetime.date so it works normally for strptime inside get_age_months
        # actually, zootecnia imports datetime directly so this mock shouldn't break strptime

        # Exact months
        self.assertEqual(get_age_months("2023-04-10"), 0)
        self.assertEqual(get_age_months("2023-03-15"), 1)
        self.assertEqual(get_age_months("2023-03-16"), 0)

        # Exact years
        self.assertEqual(get_age_months("2022-04-15"), 12)

        # Years and months
        self.assertEqual(get_age_months("2021-01-15"), 27)

        # Date in the future (months_between should return 0)
        self.assertEqual(get_age_months("2023-05-15"), 0)
