"""ФТ-01, 08, 09, 10, 12, 13, 14, 15 / ПИ-01, 08, 09, 10, 11."""
import pytest

from app.domain.errors import ConflictError, NotFoundError, ValidationError
from app.services import menu_service, order_service, slot_service, staff_service, summary_service
from tests.conftest import GUEST_A, GUEST_B, LATTE_M_OAT, LATTE_M_OAT_PRICE, new_attempt
from tests.factories import msk


def place(ctx, guest=GUEST_A, slot="10:30"):
    order, _ = order_service.place_order(ctx, guest, new_attempt(), [LATTE_M_OAT], "", slot,
                                         LATTE_M_OAT_PRICE)
    return order


def test_guest_sees_only_own_orders(ctx):
    order = place(ctx)
    assert [o["id"] for o in order_service.list_guest_orders(ctx, GUEST_A)] == [order["id"]]
    assert order_service.list_guest_orders(ctx, GUEST_B) == []
    with pytest.raises(NotFoundError):
        order_service.get_guest_order(ctx, GUEST_B, order["id"])
    with pytest.raises(NotFoundError):
        order_service.guest_cancel(ctx, GUEST_B, order["id"])


def test_full_path_and_first_timestamps(ctx, clock):
    order = place(ctx)
    clock.advance(minutes=5)
    o = staff_service.advance(ctx, order["id"], "accepted")
    assert o["status"] == "preparing" and o["preparing_at"]
    clock.advance(minutes=5)
    o = staff_service.advance(ctx, order["id"], "preparing")
    assert o["status"] == "ready"
    ready_at = o["ready_at"]
    clock.advance(minutes=5)
    o = staff_service.advance(ctx, order["id"], "ready")
    assert o["status"] == "issued" and o["finished_at"] and o["ready_at"] == ready_at
    assert [e["new_status"] for e in o["events"]] == ["accepted", "preparing", "ready", "issued"]
    assert all(e["actor"] for e in o["events"])
    with pytest.raises(ConflictError):
        staff_service.advance(ctx, order["id"], "issued")    # конечный


def test_stale_command_rejected_with_actual_state(ctx):
    order = place(ctx)
    staff_service.advance(ctx, order["id"], "accepted")
    with pytest.raises(ConflictError) as e:
        staff_service.advance(ctx, order["id"], "accepted")  # вторая вкладка
    assert e.value.code == "stale"
    assert e.value.details["order"]["status"] == "preparing"


def test_guest_cancel_releases_capacity_once(ctx):
    order = place(ctx)
    assert slot_service.usage(ctx, "10:30") == (6, 1)
    o = order_service.guest_cancel(ctx, GUEST_A, order["id"])
    assert o["status"] == "cancelled" and o["cancel_reason"] == "Отменён гостем"
    assert o["cancelled_by"] == "guest"
    assert slot_service.usage(ctx, "10:30") == (6, 0)
    with pytest.raises(ConflictError):
        order_service.guest_cancel(ctx, GUEST_A, order["id"])
    assert slot_service.usage(ctx, "10:30") == (6, 0)


def test_first_saved_action_wins(ctx):
    order = place(ctx)
    staff_service.advance(ctx, order["id"], "accepted")
    with pytest.raises(ConflictError) as e:
        order_service.guest_cancel(ctx, GUEST_A, order["id"])
    assert "сотрудник" in e.value.message.lower()
    assert slot_service.usage(ctx, "10:30") == (6, 1)


def test_staff_cancel_requires_reason_and_keeps_capacity_after_start(ctx):
    order = place(ctx)
    with pytest.raises(ValidationError):
        staff_service.staff_cancel(ctx, order["id"], "accepted", "  ")
    staff_service.advance(ctx, order["id"], "accepted")
    o = staff_service.staff_cancel(ctx, order["id"], "preparing", "Закончилось овсяное молоко")
    assert o["status"] == "cancelled" and o["cancelled_by"] == "staff"
    assert o["cancel_reason"] == "Закончилось овсяное молоко"
    assert slot_service.usage(ctx, "10:30") == (6, 1)


def test_staff_cancel_before_start_releases(ctx):
    order = place(ctx)
    staff_service.staff_cancel(ctx, order["id"], "accepted", "Пожелание меняет состав")
    assert slot_service.usage(ctx, "10:30") == (6, 0)


def test_queue_order(ctx, clock):
    late = place(ctx, slot="11:00")
    clock.advance(minutes=1)
    early1 = place(ctx, guest=GUEST_B, slot="10:30")
    clock.advance(minutes=1)
    early2 = place(ctx, slot="10:30")
    ids = [o["id"] for o in staff_service.queue(ctx)]
    assert ids == [early1["id"], early2["id"], late["id"]]


def test_not_received_forbidden_before_close(ctx):
    place(ctx)
    with pytest.raises(ConflictError):
        staff_service.close_day(ctx)


def test_close_day(ctx, clock):
    a, b, c, d = place(ctx), place(ctx), place(ctx), place(ctx, slot="11:00")
    staff_service.advance(ctx, b["id"], "accepted")
    staff_service.advance(ctx, c["id"], "accepted")
    staff_service.advance(ctx, c["id"], "preparing")
    staff_service.advance(ctx, d["id"], "accepted")
    staff_service.advance(ctx, d["id"], "preparing")
    staff_service.advance(ctx, d["id"], "ready")
    clock.set(msk(21, 5))
    result = staff_service.close_day(ctx)
    assert result == {"cancelled": 2, "not_received": 1}
    statuses = {o["id"]: o for o in staff_service.queue(ctx)}
    assert statuses[a["id"]]["cancel_reason"] == "Не выполнен до закрытия"
    assert statuses[b["id"]]["status"] == "cancelled"
    assert statuses[c["id"]]["status"] == "not_received"
    assert statuses[d["id"]]["status"] == "issued"
    events_before = sum(len(o["events"]) for o in staff_service.queue(ctx))
    assert staff_service.close_day(ctx) == {"cancelled": 0, "not_received": 0}
    assert sum(len(o["events"]) for o in staff_service.queue(ctx)) == events_before


def test_summary(ctx, clock):
    empty = summary_service.daily_summary(ctx)
    assert empty["total"] == 0 and empty["readiness"]["text"] == "Нет данных"
    a = place(ctx)                              # окно 10:30–10:45
    b = place(ctx)
    place(ctx)
    staff_service.advance(ctx, a["id"], "accepted")
    staff_service.advance(ctx, b["id"], "accepted")
    clock.set(msk(10, 40))
    staff_service.advance(ctx, a["id"], "preparing")   # вовремя
    clock.set(msk(10, 50))
    staff_service.advance(ctx, b["id"], "preparing")   # поздно
    staff_service.staff_cancel(ctx, b["id"], "ready", "Гость не пришёл, напиток остыл")
    s = summary_service.daily_summary(ctx)
    assert s["total"] == 3
    assert s["readiness"]["text"] == "50%"
    assert s["by_status"]["Отменён"] == 1
    assert s["overdue_active"] == ["001", "003"]
    assert {d["number"]: d["seconds"] for d in s["durations"]} == {"001": 2400, "002": 3000}


def test_cart_check_for_favorite_repeat(ctx):
    menu_service.set_drink_available(ctx, "latte", False)
    res = menu_service.check_cart(ctx, [LATTE_M_OAT, {"drink_id": "espresso", "size": "S", "qty": 1}])
    assert res["lines"][0]["problem"] and "недоступ" in res["lines"][0]["problem"]
    assert res["lines"][1]["problem"] is None and res["lines"][1]["line_total"] == 15000
    assert res["ok"] is False
