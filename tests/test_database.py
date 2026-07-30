import pytest
from database import convert_quantity

def test_convert_quantity_none_qty():
    assert convert_quantity(None, "kg", "ton") is None

def test_convert_quantity_same_units():
    assert convert_quantity(10.0, "kg", "kg") == 10.0
    assert convert_quantity(10.0, "Kg ", " kG") == 10.0
    assert convert_quantity(10.0, None, None) == 10.0
    assert convert_quantity(10.0, "", "") == 10.0

def test_convert_quantity_compatible_units():
    # peso
    assert convert_quantity(1.0, "ton", "kg") == 1000.0
    assert convert_quantity(1.0, "t", "kg") == 1000.0
    assert convert_quantity(1000.0, "kg", "ton") == 1.0
    assert convert_quantity(1.0, "kg", "g") == 1000.0
    assert convert_quantity(1000.0, "g", "kg") == 1.0

    # volume
    assert convert_quantity(1.0, "litro", "ml") == 1000.0
    assert convert_quantity(1.0, "l", "ml") == 1000.0
    assert convert_quantity(1000.0, "ml", "litro") == 1.0

def test_convert_quantity_mixed_case_and_spaces():
    assert convert_quantity(1.0, " tON ", " kG ") == 1000.0
    assert convert_quantity(1000.0, "ML", "lItro") == 1.0

def test_convert_quantity_incompatible_units():
    assert convert_quantity(1.0, "kg", "litro") is None
    assert convert_quantity(1.0, "ton", "ml") is None

def test_convert_quantity_unknown_units():
    assert convert_quantity(1.0, "kg", "saco") is None
    assert convert_quantity(1.0, "saco", "kg") is None
    assert convert_quantity(1.0, "saco", "caixa") is None

def test_convert_quantity_none_and_empty_units():
    assert convert_quantity(1.0, "kg", None) is None
    assert convert_quantity(1.0, None, "kg") is None
    assert convert_quantity(1.0, "kg", "") is None
    assert convert_quantity(1.0, "", "kg") is None
