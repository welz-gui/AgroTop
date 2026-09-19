import unittest

from services.constantes import (
    CARCASS_YIELD,
    KG_PER_ARROBA,
    UA_WEIGHT,
    AGE_BANDS
)

class TestConstantes(unittest.TestCase):

    def test_numeric_constants_values_and_types(self):
        """Testa se as constantes numéricas possuem os valores e tipos esperados."""
        self.assertIsInstance(CARCASS_YIELD, float)
        self.assertEqual(CARCASS_YIELD, 0.52)

        self.assertIsInstance(KG_PER_ARROBA, float)
        self.assertEqual(KG_PER_ARROBA, 15.0)

        self.assertIsInstance(UA_WEIGHT, float)
        self.assertEqual(UA_WEIGHT, 450.0)

    def test_age_bands(self):
        """Testa a lista de faixas etárias (AGE_BANDS)."""
        self.assertIsInstance(AGE_BANDS, list)
        self.assertEqual(len(AGE_BANDS), 4)

        expected_bands = [
            "Até 12 meses",
            "13 a 24 meses",
            "25 a 36 meses",
            "+ de 36 meses"
        ]

        self.assertEqual(AGE_BANDS, expected_bands)

if __name__ == '__main__':
    unittest.main()
