"""Гостевые операции: надёжный приём (ФТ-06, 07), просмотр (ФТ-08), отмена гостем (ФТ-10)."""
from __future__ import annotations

import json
import re
import uuid

from app.domain.cart import cart_total, check_quantity, fingerprint, parse_cart, price_lines, total_quantity
from app.domain.errors import ConflictError, NotFoundError, ValidationError
from app.domain.slots import acceptance_block_reason, bookable, find_slot, local_day
from app.domain.statuses import GUEST_CANCEL_REASON, Status, can_guest_cancel, releases_capacity
from app.domain.wish import normalize_wish
from app.services import orders_repo, slot_service
from app.services.context import Context
from app.services.menu_service import load_menu, load_point

_ATTEMPT_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_insert_event = orders_repo.insert_event   # точка подмены для испытаний отказа сохранения


def _check_attempt_id(attempt_id) -> str:
    if not isinstance(attempt_id, str) or not _ATTEMPT_RE.match(attempt_id):
        raise ValidationError("Некорректный идентификатор попытки оформления")
    return attempt_id


def _find_replay(conn, guest: str, attempt_id: str, fp: str) -> dict | None:
    row = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        return None
    if row["guest_hash"] != guest or row["fingerprint"] != fp:
        raise ConflictError(
            "Эта попытка оформления уже использована для другого содержимого. Подтвердите заказ заново.",
            code="attempt_reused",
        )
    return orders_repo.fetch_card(conn, row["order_id"])


def place_order(ctx: Context, guest: str, attempt_id, raw_items, raw_wish, slot_key, expected_total):
    """Возвращает (карточка, повтор). Всё или ничего: заказ, условия, резерв, очередь, событие."""
    attempt_id = _check_attempt_id(attempt_id)
    lines = parse_cart(raw_items)
    check_quantity(lines, ctx.profile)
    wish = normalize_wish(raw_wish, ctx.profile.wish_max)
    if not isinstance(expected_total, int) or isinstance(expected_total, bool):
        raise ValidationError("Не передана подтверждённая сумма заказа")
    fp = fingerprint(lines, wish, str(slot_key))

    with ctx.db.transaction() as conn:
        replay = _find_replay(conn, guest, attempt_id, fp)
        if replay is not None:
            return replay, True

        now = ctx.clock.now()
        point = load_point(conn)
        block = acceptance_block_reason(now, ctx.profile, point["paused"])
        if block:
            raise ConflictError(block, code="acceptance_closed")

        priced = price_lines(lines, load_menu(conn))
        total = cart_total(priced)

        day = local_day(now, ctx.profile)
        slot = find_slot(day, slot_key, ctx.profile)
        if slot is None or not bookable(slot, now, ctx.profile):
            raise ConflictError("Выбранное время получения больше недоступно. Выберите другой интервал.",
                                code="slot_unavailable")
        if total != expected_total:
            raise ConflictError(
                "Условия заказа изменились. Проверьте новую сумму и подтвердите заказ ещё раз.",
                code="conditions_changed",
                details={"total": total, "lines": [p.to_dict() for p in priced]},
            )
        slot_service.reserve(conn, day, slot.key, total_quantity(lines), ctx.profile.default_limit)

        order_id = str(uuid.uuid4())
        count = conn.execute("SELECT COUNT(*) FROM orders WHERE day = ?", (day.isoformat(),)).fetchone()[0]
        number = f"{count + 1:03d}"
        at = now.isoformat()
        conn.execute(
            "INSERT INTO orders (id, number, day, guest_hash, attempt_id, point_name, point_address,"
            " slot_key, slot_start, slot_end, status, total, wish, accepted_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (order_id, number, day.isoformat(), guest, attempt_id, point["name"], point["address"],
             slot.key, slot.start.isoformat(), slot.end.isoformat(), Status.ACCEPTED.value,
             total, wish, at),
        )
        for pos, p in enumerate(priced):
            conn.execute(
                "INSERT INTO order_lines (order_id, pos, drink_id, drink_name, size, addons_json,"
                " unit_price, qty, line_total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, pos, p.drink_id, p.drink_name, p.size,
                 json.dumps([{"id": a.id, "name": a.name, "price": a.price} for a in p.addons],
                            ensure_ascii=False),
                 p.unit_price, p.qty, p.line_total),
            )
        _insert_event(conn, order_id, None, Status.ACCEPTED.value, at, "guest")
        conn.execute("INSERT INTO attempts (id, guest_hash, fingerprint, order_id, created_at)"
                     " VALUES (?, ?, ?, ?, ?)", (attempt_id, guest, fp, order_id, at))
        return orders_repo.fetch_card(conn, order_id), False


def get_attempt(ctx: Context, guest: str, attempt_id) -> dict:
    """Выяснить исход попытки при неизвестном результате отправки."""
    attempt_id = _check_attempt_id(attempt_id)
    with ctx.db.read() as conn:
        row = conn.execute("SELECT order_id FROM attempts WHERE id = ? AND guest_hash = ?",
                           (attempt_id, guest)).fetchone()
        if row is None:
            raise NotFoundError("Заказ по этой попытке не принят", code="attempt_not_found")
        return orders_repo.fetch_card(conn, row["order_id"])


def list_guest_orders(ctx: Context, guest: str) -> list[dict]:
    with ctx.db.read() as conn:
        rows = conn.execute("SELECT * FROM orders WHERE guest_hash = ? ORDER BY accepted_at DESC, number DESC",
                            (guest,)).fetchall()
        return [orders_repo.to_card(conn, r) for r in rows]


def _own_row(conn, guest: str, order_id: str):
    row = orders_repo.fetch_row(conn, order_id) if isinstance(order_id, str) else None
    if row is None or row["guest_hash"] != guest:
        raise NotFoundError("Заказ не найден")
    return row


def get_guest_order(ctx: Context, guest: str, order_id: str) -> dict:
    with ctx.db.read() as conn:
        return orders_repo.to_card(conn, _own_row(conn, guest, order_id))


def guest_cancel(ctx: Context, guest: str, order_id: str) -> dict:
    with ctx.db.transaction() as conn:
        row = _own_row(conn, guest, order_id)
        status = Status(row["status"])
        if not can_guest_cancel(status):
            raise ConflictError(
                f"Заказ уже в статусе «{status.label}» — самостоятельная отмена недоступна. "
                "Обратитесь к сотруднику.",
                code="cannot_cancel", details={"order": orders_repo.to_card(conn, row)},
            )
        at = ctx.now_iso()
        conn.execute(
            "UPDATE orders SET status = ?, cancelled_by = 'guest', cancel_reason = ?, finished_at = ?"
            " WHERE id = ?",
            (Status.CANCELLED.value, GUEST_CANCEL_REASON, at, order_id),
        )
        if releases_capacity(status):
            slot_service.release(conn, row["day"], row["slot_key"], orders_repo.order_qty(conn, order_id))
        _insert_event(conn, order_id, status.value, Status.CANCELLED.value, at, "guest", GUEST_CANCEL_REASON)
        return orders_repo.fetch_card(conn, order_id)
