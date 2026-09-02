import pytest
from app import normalize_name, normalize_phone


@pytest.mark.parametrize("raw,expected", [
    ("joão da silva", "João Da Silva"),
    ("ANNA-maria o'neill", "Anna-Maria O'neill"),
    ("  pedro   alves  ", "Pedro Alves"),
    ("mARIA-CLARA dos santos", "Maria-Clara Dos Santos"),
    ("", ""),
    (None, ""),
    ("léia", "Léia"),
    ("  maria   de   lourdes  ", "Maria De Lourdes"),
    ("joão-pedro   o'neill", "João-Pedro O'neill"),
])
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("(99) 99999-9999", "+5599999999999"),
    ("+55 (99) 99999-9999", "+5599999999999"),
    ("+5511999999999", "+5511999999999"),
    ("11999999999", "+5511999999999"),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected
