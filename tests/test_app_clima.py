import unittest
from unittest.mock import patch, MagicMock
import app
import json
import urllib.error

class TestAppClima(unittest.TestCase):
    def setUp(self):
        # Clear Streamlit cache before each test
        app._fetch_forecast.clear()

    @patch('urllib.request.urlopen')
    def test_fetch_forecast_exception_returns_none(self, mock_urlopen):
        """Test that _fetch_forecast returns None on network exception."""
        mock_urlopen.side_effect = urllib.error.URLError("Network error")
        result = app._fetch_forecast(-15.6, -56.1)
        self.assertIsNone(result)

    @patch('urllib.request.urlopen')
    def test_fetch_forecast_timeout_returns_none(self, mock_urlopen):
        """Test that _fetch_forecast returns None on timeout."""
        mock_urlopen.side_effect = TimeoutError("Timeout")
        result = app._fetch_forecast(-15.6, -56.1)
        self.assertIsNone(result)

    @patch('urllib.request.urlopen')
    def test_fetch_forecast_success(self, mock_urlopen):
        """Test that _fetch_forecast returns parsed JSON on success."""
        mock_response = MagicMock()
        expected_data = {"daily": {"temperature_2m_max": [30.0]}}
        mock_response.read.return_value = json.dumps(expected_data).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = app._fetch_forecast(-15.6, -56.1)

        self.assertEqual(result, expected_data)

if __name__ == '__main__':
    unittest.main()
