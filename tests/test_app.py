import unittest
import sys
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import _fmt_dose

class TestApp(unittest.TestCase):
    def test_fmt_dose_valid_float(self):
        self.assertEqual(_fmt_dose(10.0, 'ml'), '10,0 ml')
        self.assertEqual(_fmt_dose(1, 'comprimido'), '1,0 comprimido')
        self.assertEqual(_fmt_dose(2.5, 'dose'), '2,5 doses')

    def test_fmt_dose_invalid_type(self):
        # Trigger ValueError/TypeError
        self.assertEqual(_fmt_dose("abc", 'ml'), "abc ml")
        self.assertEqual(_fmt_dose(None, 'dose'), "None dose")

if __name__ == '__main__':
    unittest.main()
