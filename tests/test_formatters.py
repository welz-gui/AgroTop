import unittest
from app import _num_br

class TestFormatters(unittest.TestCase):
    def test_num_br(self):
        self.assertEqual(_num_br(10.0), "10,0")
        self.assertEqual(_num_br(10.5), "10,5")
        self.assertEqual(_num_br(10.55, casas=2), "10,55")
        self.assertEqual(_num_br(0), "0,0")
        self.assertEqual(_num_br(-5.2), "-5,2")
        self.assertEqual(_num_br("10.0"), "10,0")
        self.assertEqual(_num_br("10.5"), "10,5")

        # Error conditions -> returns str(v)
        self.assertEqual(_num_br("invalid"), "invalid")
        self.assertEqual(_num_br(None), "None")

if __name__ == '__main__':
    unittest.main()
