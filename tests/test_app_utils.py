import unittest
from unittest.mock import patch
import app

class TestAppUtils(unittest.TestCase):
    @patch('PIL.Image.open')
    def test_decode_qr_exception(self, mock_image_open):
        mock_image_open.side_effect = Exception("Mocked error")
        result = app._decode_qr(b'raw_data')
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
