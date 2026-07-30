import pytest
from app import _plural

def test_plural_default_plural():
    # Test cases without an explicit plural argument (defaults to adding 's')
    assert _plural(1, "animal") == "1 animal"
    assert _plural(2, "animal") == "2 animals"
    assert _plural(0, "animal") == "0 animals"
    assert _plural(1, "teste") == "1 teste"
    assert _plural(5, "teste") == "5 testes"

def test_plural_explicit_plural():
    # Test cases with an explicit plural argument
    assert _plural(1, "animal", "animais") == "1 animal"
    assert _plural(3, "animal", "animais") == "3 animais"
    assert _plural(0, "animal", "animais") == "0 animais"
    assert _plural(1, "vez", "vezes") == "1 vez"
    assert _plural(10, "vez", "vezes") == "10 vezes"
