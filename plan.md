1. **Import `_parse_date` in `tests/test_qualidade.py`**.
2. **Add `TestParseDate` class to `tests/test_qualidade.py`**:
   - Write `test_parse_date_valid`: tests a valid date string.
   - Write `test_parse_date_invalid_format`: tests malformed strings (ValueError).
   - Write `test_parse_date_invalid_type`: tests invalid types like `None` or `int` (TypeError).
3. **Run tests** using `python -m pytest tests/test_qualidade.py` to ensure they pass.
4. **Complete pre-commit steps** to ensure testing and reviews are done properly.
5. **Submit the PR** with descriptive title and body.
