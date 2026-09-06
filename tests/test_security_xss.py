import unittest
from unittest.mock import patch
import app

class TestSecurityXSS(unittest.TestCase):
    @patch('app.st')
    def test_keypad_display_escapes_html(self, mock_st):
        # Setup session state mock
        mock_st.session_state = type('SessionState', (), {'keypad_value': '<img src=x onerror=alert(1)>'})()

        # Access the wrapped function directly if it's wrapped by st.fragment
        if hasattr(app._teclado_numerico, '__wrapped__'):
            app._teclado_numerico.__wrapped__()
        else:
            app._teclado_numerico()

        called_with_escaped = False
        for call in mock_st.markdown.call_args_list:
            if '&lt;img src=x onerror=alert(1)&gt;' in str(call):
                called_with_escaped = True
                break

        self.assertTrue(called_with_escaped, f"Calls were: {mock_st.markdown.call_args_list}")

if __name__ == '__main__':
    unittest.main()
