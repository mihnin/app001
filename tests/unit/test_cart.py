from dataclasses import replace

import pytest

from app.domain.cart import (
    CartLine, cart_total, check_quantity, fingerprint, line_problem,
    parse_cart, price_lines, total_quantity,
)
from app.domain.errors import ConflictError, ValidationError
from tests.factories import PROFILE, make_menu


def test_parse_cart_ok():
    lines = parse_cart([{"drink_id": "latte", "size": "M", "addons": ["oat", "syrup"], "qty": 2}])
    assert lines == [CartLine("latte", "M", ("oat", "syrup"), 2)]


@pytest.mark.parametrize("raw", [
    [{"drink_id": "latte", "size": "M", "qty": 0}],
    [{"drink_id": "latte", "size": "M", "qty": -1}],
    [{"drink_id": "latte", "size": "M", "qty": 1.5}],
    [{"drink_id": "latte", "size": "M", "qty": "2"}],
    [{"drink_id": "latte", "size": "M", "qty": True}],
    [{"drink_id": "", "size": "M", "qty": 1}],
    [{"drink_id": "latte", "size": "M", "addons": ["oat", "oat"], "qty": 1}],
    ["latte"],
    "latte",
])
def test_parse_cart_rejects_bad_shape(raw):
    with pytest.raises(ValidationError):
        parse_cart(raw)


def test_quantity_limits():
    one = CartLine("latte", "M", (), 1)
    with pytest.raises(ValidationError, match="пуст"):
        check_quantity([], PROFILE)
    check_quantity([replace(one, qty=4)], PROFILE)
    with pytest.raises(ValidationError, match="4"):
        check_quantity([replace(one, qty=3), replace(one, qty=2)], PROFILE)
    assert total_quantity([replace(one, qty=3), one]) == 4


def test_price_formula():
    menu = make_menu()
    priced = price_lines([
        CartLine("latte", "L", ("oat", "syrup"), 2),   # (29900+6050+4000)*2 = 79900
        CartLine("espresso", "S", (), 1),               # 15000
    ], menu)
    assert priced[0].unit_price == 39950
    assert priced[0].line_total == 79900
    assert priced[0].drink_name == "Латте"
    assert [a.name for a in priced[0].addons] == ["Овсяное молоко", "Сироп ваниль"]
    assert cart_total(priced) == 94900


def test_incompatible_size_and_addon_rejected():
    menu = make_menu()
    with pytest.raises(ValidationError, match="размер"):
        price_lines([CartLine("espresso", "L", (), 1)], menu)
    with pytest.raises(ValidationError, match="добав"):
        price_lines([CartLine("espresso", "S", ("oat",), 1)], menu)
    with pytest.raises(ValidationError):
        price_lines([CartLine("tea", "S", (), 1)], menu)


def test_unavailable_items_are_conflict():
    menu = make_menu()
    off_drink = replace(menu.drinks["latte"], available=False)
    with pytest.raises(ConflictError) as e:
        price_lines([CartLine("latte", "M", (), 1)], make_menu(latte=off_drink))
    assert e.value.code == "item_unavailable"
    off_addon = replace(menu.addons["oat"], available=False)
    with pytest.raises(ConflictError):
        price_lines([CartLine("latte", "M", ("oat",), 1)], make_menu(oat=off_addon))


def test_line_problem_reports_without_raising():
    menu = make_menu(latte=replace(make_menu().drinks["latte"], available=False))
    assert line_problem(CartLine("espresso", "S", (), 1), menu) is None
    assert "недоступ" in line_problem(CartLine("latte", "M", (), 1), menu)


def test_fingerprint_depends_on_content_not_addon_order():
    a = [CartLine("latte", "M", ("oat", "syrup"), 1)]
    b = [CartLine("latte", "M", ("syrup", "oat"), 1)]
    assert fingerprint(a, "", "10:00") == fingerprint(b, "", "10:00")
    assert fingerprint(a, "", "10:00") != fingerprint(a, "без сахара", "10:00")
    assert fingerprint(a, "", "10:00") != fingerprint(a, "", "10:15")
