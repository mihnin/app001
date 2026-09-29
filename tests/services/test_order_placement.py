"""ФТ-03, 05, 06, 07, 11, 16 / ПИ-02, 04, 05, 06, 07."""
import sqlite3
import threading

import pytest

from app.domain.errors import ConflictError, NotFoundError, UnavailableError, ValidationError
from app.services import menu_service, order_service, slot_service
from tests.conftest import GUEST_A, GUEST_B, LATTE_M_OAT, LATTE_M_OAT_PRICE, new_attempt
from tests.factories import msk


def place(ctx, guest=GUEST_A, items=None, slot="10:30", total=None, wish="", attempt=None):
    items = items if items is not None else [LATTE_M_OAT]
    total = LATTE_M_OAT_PRICE if total is None else total
    return order_service.place_order(ctx, guest, attempt or new_attempt(), items, wish, slot, total)


def test_accepts_order_and_reserves_capacity(ctx):
    order, replayed = place(ctx, wish="Погорячее, пожалуйста")
    assert not replayed
    assert order["status"] == "accepted" and order["status_label"] == "Принят"
    assert order["number"] == "001"
    assert order["total"] == LATTE_M_OAT_PRICE
    assert order["lines"][0]["drink_name"] == "Латте"
    assert order["wish"] == "Погорячее, пожалуйста"
    assert order["slot"]["key"] == "10:30"
    assert "учебн" in order["point"]["address"].lower()
    slots = slot_service.list_slots(ctx)["slots"]
    s = next(x for x in slots if x["key"] == "10:30")
    assert s["used"] == 1 and s["remaining"] == 5


def test_numbers_are_sequential(ctx):
    assert place(ctx)[0]["number"] == "001"
    assert place(ctx)[0]["number"] == "002"


def test_same_attempt_returns_same_order_without_double_reservation(ctx):
    attempt = new_attempt()
    first, _ = place(ctx, attempt=attempt)
    again, replayed = place(ctx, attempt=attempt)
    assert replayed and again["id"] == first["id"]
    assert slot_service.usage(ctx, "10:30") == (6, 1)
    assert order_service.get_attempt(ctx, GUEST_A, attempt)["id"] == first["id"]


def test_attempt_with_changed_content_is_conflict(ctx):
    attempt = new_attempt()
    place(ctx, attempt=attempt)
    with pytest.raises(ConflictError) as e:
        place(ctx, attempt=attempt, wish="другое")
    assert e.value.code == "attempt_reused"


def test_separate_identical_order_allowed(ctx):
    place(ctx)
    place(ctx)
    assert slot_service.usage(ctx, "10:30") == (6, 2)


def test_unknown_attempt_not_found(ctx):
    with pytest.raises(NotFoundError):
        order_service.get_attempt(ctx, GUEST_A, new_attempt())


def test_bad_attempt_id(ctx):
    with pytest.raises(ValidationError):
        place(ctx, attempt="x")


@pytest.mark.parametrize("items", [[], [{**LATTE_M_OAT, "qty": 5}],
                                   [{**LATTE_M_OAT, "addons": ["shot", "shot"]}],
                                   [{"drink_id": "espresso", "size": "S", "addons": ["oat"], "qty": 1}]])
def test_invalid_cart_rejected(ctx, items):
    with pytest.raises(ValidationError):
        place(ctx, items=items)


def test_price_change_requires_reconfirmation(ctx):
    with pytest.raises(ConflictError) as e:
        place(ctx, total=LATTE_M_OAT_PRICE - 100)
    assert e.value.code == "conditions_changed"
    assert e.value.details["total"] == LATTE_M_OAT_PRICE


def test_stop_list_and_pause(ctx):
    menu_service.set_addon_available(ctx, "oat", False)
    with pytest.raises(ConflictError) as e:
        place(ctx)
    assert e.value.code == "item_unavailable"
    menu_service.set_addon_available(ctx, "oat", True)
    menu_service.set_paused(ctx, True)
    with pytest.raises(ConflictError) as e:
        place(ctx)
    assert e.value.code == "acceptance_closed"


@pytest.mark.parametrize("slot", ["10:00", "10:10", "21:00", "bad"])
def test_invalid_or_too_early_slot(ctx, slot):
    with pytest.raises(ConflictError):
        place(ctx, slot=slot)


def test_closed_point(ctx, clock):
    clock.set(msk(21, 0))
    with pytest.raises(ConflictError) as e:
        place(ctx, slot="20:45")
    assert e.value.code == "acceptance_closed"
    clock.set(msk(8, 30))
    with pytest.raises(ConflictError):
        place(ctx, slot="09:00")


def test_slot_full_counts_drinks(ctx):
    four = [{**LATTE_M_OAT, "qty": 4}]
    place(ctx, items=four, total=LATTE_M_OAT_PRICE * 4)
    with pytest.raises(ConflictError) as e:
        place(ctx, items=[{**LATTE_M_OAT, "qty": 3}], total=LATTE_M_OAT_PRICE * 3)
    assert e.value.code == "slot_full"
    place(ctx, items=[{**LATTE_M_OAT, "qty": 2}], total=LATTE_M_OAT_PRICE * 2)
    assert slot_service.usage(ctx, "10:30") == (6, 6)


def test_lowering_limit_keeps_orders_and_blocks_new(ctx):
    place(ctx)
    place(ctx)
    slot_service.set_limit(ctx, "10:30", 1)
    s = next(x for x in slot_service.list_slots(ctx)["slots"] if x["key"] == "10:30")
    assert s["remaining"] == 0 and not s["available"]
    assert len(order_service.list_guest_orders(ctx, GUEST_A)) == 2
    with pytest.raises(ConflictError):
        place(ctx)


def test_concurrent_last_capacity(ctx):
    slot_service.set_limit(ctx, "10:30", 1)
    results = []

    def worker(guest):
        try:
            place(ctx, guest=guest)
            results.append("ok")
        except ConflictError as e:
            results.append(e.code)

    threads = [threading.Thread(target=worker, args=(g,)) for g in (GUEST_A, GUEST_B)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok", "slot_full"]
    assert slot_service.usage(ctx, "10:30") == (1, 1)


def test_storage_failure_leaves_no_partial_order(ctx, monkeypatch):
    attempt = new_attempt()

    def boom(*a, **k):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(order_service, "_insert_event", boom)
    with pytest.raises(UnavailableError):
        place(ctx, attempt=attempt)
    monkeypatch.undo()
    assert order_service.list_guest_orders(ctx, GUEST_A) == []
    assert slot_service.usage(ctx, "10:30") == (6, 0)
    with pytest.raises(NotFoundError):
        order_service.get_attempt(ctx, GUEST_A, attempt)
    order, replayed = place(ctx, attempt=attempt)     # та же попытка после сбоя
    assert not replayed and order["status"] == "accepted"


def test_wish_limits(ctx):
    place(ctx, wish="я" * 200)
    with pytest.raises(ValidationError):
        place(ctx, wish="я" * 201)


def test_menu_price_change_does_not_touch_accepted_order(ctx):
    order, _ = place(ctx)
    with ctx.db.transaction() as conn:
        conn.execute("UPDATE drinks SET sizes_json='{\"S\":1,\"M\":1,\"L\":1}' WHERE id='latte'")
    again = order_service.get_guest_order(ctx, GUEST_A, order["id"])
    assert again["total"] == LATTE_M_OAT_PRICE
