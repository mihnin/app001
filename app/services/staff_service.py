"""Операции сотрудника: очередь, статусы, отмена, завершение дня (ФТ-09, 10, 13)."""
from __future__ import annotations

from datetime import date, datetime

from app.domain.errors import ConflictError, NotFoundError, ValidationError
from app.domain.slots import local_day, local_now
from app.domain.statuses import (
    CLOSE_DAY_REASON, Status, can_advance, can_staff_cancel, next_status, parse_status, releases_capacity,
)
from app.services import orders_repo, slot_service
from app.services.context import Context

_FIRST_TIME_COLUMN = {
    Status.PREPARING: "preparing_at",
    Status.READY: "ready_at",
    Status.ISSUED: "finished_at",
}


def queue(ctx: Context, day: date | None = None) -> list[dict]:
    day = day or local_day(ctx.clock.now(), ctx.profile)
    with ctx.db.read() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE day = ? ORDER BY slot_start, accepted_at, number",
            (day.isoformat(),),
        ).fetchall()
        return [orders_repo.to_card(conn, r) for r in rows]


def _locked_row(conn, order_id: str, expected_status) -> tuple:
    row = orders_repo.fetch_row(conn, order_id)
    if row is None:
        raise NotFoundError("Заказ не найден")
    expected = parse_status(expected_status)
    current = Status(row["status"])
    if current != expected:
        raise ConflictError(
            f"Заказ уже в статусе «{current.label}». Показано актуальное состояние.",
            code="stale", details={"order": orders_repo.to_card(conn, row)},
        )
    return row, current


def advance(ctx: Context, order_id: str, expected_status) -> dict:
    """Следующий этап: Принят → Готовится → Готов → Выдан. Первые отметки не перезаписываются."""
    with ctx.db.transaction() as conn:
        row, current = _locked_row(conn, order_id, expected_status)
        target = next_status(current)
        if target is None or not can_advance(current, target):
            raise ConflictError(f"Из статуса «{current.label}» переход невозможен", code="final_status")
        at = ctx.now_iso()
        column = _FIRST_TIME_COLUMN[target]
        conn.execute(
            f"UPDATE orders SET status = ?, {column} = COALESCE({column}, ?) WHERE id = ?",
            (target.value, at, order_id),
        )
        orders_repo.insert_event(conn, order_id, current.value, target.value, at, "staff")
        return orders_repo.fetch_card(conn, order_id)


def _clean_reason(reason) -> str:
    if not isinstance(reason, str) or len(reason.strip()) < 3:
        raise ValidationError("Укажите содержательную причину отмены (не короче 3 символов)")
    reason = reason.strip()
    if len(reason) > 200:
        raise ValidationError("Причина отмены длиннее 200 символов")
    return reason


def _cancel(conn, row, current: Status, reason: str, at: str, actor: str) -> None:
    conn.execute(
        "UPDATE orders SET status = ?, cancelled_by = ?, cancel_reason = ?,"
        " finished_at = COALESCE(finished_at, ?) WHERE id = ?",
        (Status.CANCELLED.value, actor, reason, at, row["id"]),
    )
    if releases_capacity(current):
        slot_service.release(conn, row["day"], row["slot_key"], orders_repo.order_qty(conn, row["id"]))
    orders_repo.insert_event(conn, row["id"], current.value, Status.CANCELLED.value, at, actor, reason)


def staff_cancel(ctx: Context, order_id: str, expected_status, reason) -> dict:
    reason = _clean_reason(reason)
    with ctx.db.transaction() as conn:
        row, current = _locked_row(conn, order_id, expected_status)
        if not can_staff_cancel(current):
            raise ConflictError(f"Заказ в конечном статусе «{current.label}»", code="final_status")
        _cancel(conn, row, current, reason, ctx.now_iso(), "staff")
        return orders_repo.fetch_card(conn, order_id)


def _closed(ctx: Context, day: date) -> bool:
    now = local_now(ctx.clock.now(), ctx.profile)
    close = datetime.combine(day, ctx.profile.close_time, tzinfo=ctx.profile.tz)
    return now >= close


def close_day(ctx: Context, day: date | None = None) -> dict:
    """После закрытия: «Принят»/«Готовится» → отмена, «Готов» → «Не получен». Повтор без новых событий."""
    day = day or local_day(ctx.clock.now(), ctx.profile)
    if not _closed(ctx, day):
        raise ConflictError(
            f"Завершить день можно только после закрытия ({ctx.profile.close_time.strftime('%H:%M')})",
            code="not_closed_yet",
        )
    result = {"cancelled": 0, "not_received": 0}
    with ctx.db.transaction() as conn:
        at = ctx.now_iso()
        rows = conn.execute("SELECT * FROM orders WHERE day = ? AND status IN (?, ?, ?)",
                            (day.isoformat(), Status.ACCEPTED.value, Status.PREPARING.value,
                             Status.READY.value)).fetchall()
        for row in rows:
            current = Status(row["status"])
            if current == Status.READY:
                conn.execute("UPDATE orders SET status = ?, finished_at = COALESCE(finished_at, ?)"
                             " WHERE id = ?", (Status.NOT_RECEIVED.value, at, row["id"]))
                orders_repo.insert_event(conn, row["id"], current.value, Status.NOT_RECEIVED.value, at, "staff")
                result["not_received"] += 1
            else:
                _cancel(conn, row, current, CLOSE_DAY_REASON, at, "staff")
                result["cancelled"] += 1
    return result
