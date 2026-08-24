import unittest
from datetime import date
from unittest.mock import patch

from services.zootecnia import (
    get_age_display,
    get_age_months,
    calculate_gmd_total,
    estimate_weight_by_measurement,
    kg_to_arrobas,
)


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


class TestZootecniaCalculateGMDTotal(unittest.TestCase):
    @patch("services.zootecnia.date")
    def test_calculate_gmd_total_happy_path(self, mock_date):
        mock_date.today.return_value = date(2024, 1, 10)
        mock_date.fromisoformat.side_effect = date.fromisoformat

        animal = {
            "entry_date": "2024-01-01",
            "current_weight": 300.0,
            "entry_weight": 200.0
        }
        # 9 days diff. (300 - 200) / 9 = 11.111
        result = calculate_gmd_total(animal)
        self.assertAlmostEqual(result, 11.111, places=3)

    @patch("services.zootecnia.date")
    def test_calculate_gmd_total_zero_days(self, mock_date):
        mock_date.today.return_value = date(2024, 1, 1)
        mock_date.fromisoformat.side_effect = date.fromisoformat

        animal = {
            "entry_date": "2024-01-01",
            "current_weight": 300.0,
            "entry_weight": 200.0
        }
        # 0 days diff
        result = calculate_gmd_total(animal)
        self.assertIsNone(result)

    @patch("services.zootecnia.date")
    def test_calculate_gmd_total_negative_days(self, mock_date):
        mock_date.today.return_value = date(2023, 12, 31)
        mock_date.fromisoformat.side_effect = date.fromisoformat

        animal = {
            "entry_date": "2024-01-01",
            "current_weight": 300.0,
            "entry_weight": 200.0
        }
        # negative days diff
        result = calculate_gmd_total(animal)
        self.assertIsNone(result)

    def test_calculate_gmd_total_invalid_date(self):
        animal = {
            "entry_date": "invalid-date",
            "current_weight": 300.0,
            "entry_weight": 200.0
        }
        result = calculate_gmd_total(animal)
        self.assertIsNone(result)

    def test_calculate_gmd_total_missing_keys(self):
        animal = {
            "current_weight": 300.0,
            "entry_weight": 200.0
        }
        result = calculate_gmd_total(animal)
        self.assertIsNone(result)

        animal_2 = {
            "entry_date": "2024-01-01",
            "entry_weight": 200.0
        }
        result_2 = calculate_gmd_total(animal_2)
        self.assertIsNone(result_2)

    @patch("services.zootecnia.date")
    def test_calculate_gmd_total_type_error(self, mock_date):
        mock_date.today.return_value = date(2024, 1, 10)
        mock_date.fromisoformat.side_effect = date.fromisoformat

        animal = {
            "entry_date": "2024-01-01",
            "current_weight": "300.0",
            "entry_weight": 200.0
        }
        result = calculate_gmd_total(animal)
        self.assertIsNone(result)

    def test_empty_dict_returns_none(self):
        # Sem entry_date/current_weight/entry_weight -> KeyError
        self.assertIsNone(calculate_gmd_total({}))

    def test_none_animal_returns_none(self):
        # None como animal -> TypeError ao indexar
        self.assertIsNone(calculate_gmd_total(None))


class TestZootecniaEstimateWeight(unittest.TestCase):
    def test_zero_or_negative_measurements(self):
        # Test girth_cm <= 0
        self.assertEqual(estimate_weight_by_measurement(0, 100), 0.0)
        self.assertEqual(estimate_weight_by_measurement(-10, 100), 0.0)

        # Test length_cm <= 0
        self.assertEqual(estimate_weight_by_measurement(100, 0), 0.0)
        self.assertEqual(estimate_weight_by_measurement(100, -10), 0.0)

        # Test both <= 0
        self.assertEqual(estimate_weight_by_measurement(0, 0), 0.0)
        self.assertEqual(estimate_weight_by_measurement(-10, -10), 0.0)

    def test_valid_measurements(self):
        # Calculation: (100^2 * 100) / 10838 = 1000000 / 10838 = 92.26... -> 92.3
        self.assertEqual(estimate_weight_by_measurement(100, 100), 92.3)

        # Calculation: (150^2 * 150) / 10838 = 3375000 / 10838 = 311.404... -> 311.4
        self.assertEqual(estimate_weight_by_measurement(150, 150), 311.4)

        # Calculation: (200^2 * 160) / 10838 = 6400000 / 10838 = 590.51... -> 590.5
        self.assertEqual(estimate_weight_by_measurement(200, 160), 590.5)

    def test_float_measurements(self):
        # Calculation: (100.5^2 * 105.2) / 10838 = (10100.25 * 105.2) / 10838 = 1062546.3 / 10838 = 98.03... -> 98.0
        self.assertEqual(estimate_weight_by_measurement(100.5, 105.2), 98.0)


class TestZootecniaKgToArrobas(unittest.TestCase):
    def test_default_yield(self):
        # 300 kg * 0.52 / 15.0 = 10.4
        self.assertEqual(kg_to_arrobas(300), 10.4)

        # 450 kg * 0.52 / 15.0 = 15.6
        self.assertEqual(kg_to_arrobas(450), 15.6)

    def test_custom_yield(self):
        # 300 kg * 0.50 / 15.0 = 10.0
        self.assertEqual(kg_to_arrobas(300, yield_=0.50), 10.0)

    def test_zero_weight(self):
        self.assertEqual(kg_to_arrobas(0), 0.0)

    def test_rounding(self):
        # 333 kg * 0.52 / 15.0 = 11.544 -> 11.54
        self.assertEqual(kg_to_arrobas(333), 11.54)

        # 334 kg * 0.52 / 15.0 = 11.578666... -> 11.58
        self.assertEqual(kg_to_arrobas(334), 11.58)
