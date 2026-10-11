import unittest
from unittest.mock import patch

from app import _compress_image

class TestAppCompressImage(unittest.TestCase):
    @patch('PIL.Image.open')
    def test_compress_image_error_path(self, mock_open):
        mock_open.side_effect = Exception("Mocked exception")

        raw_data = b"fake_image_data"
        result = _compress_image(raw_data)

        self.assertEqual(result, raw_data)

if __name__ == '__main__':
    unittest.main()
