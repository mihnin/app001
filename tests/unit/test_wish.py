import pytest

from app.domain.errors import ValidationError
from app.domain.wish import normalize_wish, wish_length


def test_empty_wish_allowed():
    assert normalize_wish(None, 200) == ""
    assert normalize_wish("   \n ", 200) == ""


def test_boundary_length():
    assert normalize_wish("я" * 200, 200) == "я" * 200
    with pytest.raises(ValidationError, match="200"):
        normalize_wish("я" * 201, 200)


def test_crlf_counts_as_one_char():
    text = "а\r\nб"
    assert normalize_wish(text, 200) == "а\nб"
    assert wish_length(text) == 3


def test_markup_kept_as_plain_text():
    assert normalize_wish("<b>горячее</b>", 200) == "<b>горячее</b>"


def test_non_string_rejected():
    with pytest.raises(ValidationError):
        normalize_wish(123, 200)
