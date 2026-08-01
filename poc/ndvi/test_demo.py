import datetime
import unittest

import pandas as pd

from poc.ndvi.demo import largest_gap, threshold_usage


class LargestGapTest(unittest.TestCase):
    def test_inclui_inicio_e_fim_do_periodo(self):
        dates = pd.Series(pd.to_datetime(["2025-05-11", "2025-05-21"]))

        gap = largest_gap(
            dates,
            start_date=datetime.date(2025, 5, 1),
            end_date=datetime.date(2025, 6, 20),
        )

        self.assertEqual(gap, 30)

    def test_serie_vazia_retorna_periodo_inteiro(self):
        gap = largest_gap(
            pd.Series([], dtype="datetime64[ns]"),
            start_date=datetime.date(2025, 5, 1),
            end_date=datetime.date(2025, 5, 31),
        )

        self.assertEqual(gap, 30)

    def test_limiar_e_aplicado_antes_do_calculo(self):
        scenes = pd.DataFrame({
            "date": pd.to_datetime(["2025-05-02", "2025-05-12", "2025-05-29"]),
            "cloud_cover": [5.0, 30.0, 8.0],
        })
        usable = threshold_usage(scenes, 10.0)

        gap = largest_gap(
            usable["date"],
            start_date=datetime.date(2025, 5, 1),
            end_date=datetime.date(2025, 5, 31),
        )

        self.assertEqual(gap, 27)


if __name__ == "__main__":
    unittest.main()
