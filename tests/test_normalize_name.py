import pytest
from app import normalize_name


@pytest.mark.parametrize("raw,expected", [
    ("joão da silva", "João Da Silva"),
    ("ANNA-maria o'neill", "Anna-Maria O'neill"),
    ("  pedro   alves  ", "Pedro Alves"),
    ("mARIA-CLARA dos santos", "Maria-Clara Dos Santos"),
    ("", ""),
    (None, ""),
    ("léia", "Léia"),
])
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected
