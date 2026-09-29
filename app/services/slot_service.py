"""Ёмкость интервалов: остатки, лимиты, резервирование (ФТ-05, ФТ-11)."""
from __future__ import annotations

from datetime import date

from app.domain.errors import ConflictError, NotFoundError, ValidationError
from app.domain.slots import acceptance_block_reason, bookable, day_grid, find_slot, local_day, remaining
from app.services.context import Context
from app.services.menu_service import load_point


def _usage_map(conn, day: date) -> dict[str, tuple[int, int]]:
    rows = conn.execute("SELECT start, lim, used FROM slot_limits WHERE day = ?", (day.isoformat(),))
    return {r["start"]: (r["lim"], r["used"]) for r in rows}


def usage(ctx: Context, key: str, day: date | None = None) -> tuple[int, int]:
    day = day or local_day(ctx.clock.now(), ctx.profile)
    with ctx.db.read() as conn:
        return _usage_map(conn, day).get(key, (ctx.profile.default_limit, 0))


def list_slots(ctx: Context, qty: int = 1) -> dict:
    now = ctx.clock.now()
    day = local_day(now, ctx.profile)
    with ctx.db.read() as conn:
        point = load_point(conn)
        umap = _usage_map(conn, day)
    block = acceptance_block_reason(now, ctx.profile, point["paused"])
    slots = []
    for slot in day_grid(day, ctx.profile):
        lim, used = umap.get(slot.key, (ctx.profile.default_limit, 0))
        rest = remaining(lim, used)
        reason = None
        if block:
            reason = block
        elif not bookable(slot, now, ctx.profile):
            reason = "Время уже недоступно для заказа"
        elif rest < qty:
            reason = "Интервал заполнен" if rest == 0 else f"Осталось мест: {rest}"
        slots.append({
            "key": slot.key, "start": slot.start.isoformat(), "end": slot.end.isoformat(),
            "limit": lim, "used": used, "remaining": rest,
            "available": reason is None, "reason": reason,
        })
    return {"day": day.isoformat(), "block_reason": block, "slots": slots}


def set_limit(ctx: Context, key: str, limit) -> dict:
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
        raise ValidationError("Лимит должен быть целым неотрицательным числом")
    day = local_day(ctx.clock.now(), ctx.profile)
    if find_slot(day, key, ctx.profile) is None:
        raise NotFoundError(f"Интервал {key} не существует")
    with ctx.db.transaction() as conn:
        conn.execute(
            "INSERT INTO slot_limits (day, start, lim, used) VALUES (?, ?, ?, 0) "
            "ON CONFLICT (day, start) DO UPDATE SET lim = excluded.lim",
            (day.isoformat(), key, limit),
        )
        lim, used = _usage_map(conn, day)[key]
    return {"key": key, "limit": lim, "used": used, "remaining": remaining(lim, used)}


def reserve(conn, day: date, key: str, qty: int, default_limit: int) -> None:
    """Вызывается внутри транзакции приёма."""
    conn.execute("INSERT OR IGNORE INTO slot_limits (day, start, lim, used) VALUES (?, ?, ?, 0)",
                 (day.isoformat(), key, default_limit))
    row = conn.execute("SELECT lim, used FROM slot_limits WHERE day = ? AND start = ?",
                       (day.isoformat(), key)).fetchone()
    rest = remaining(row["lim"], row["used"])
    if rest < qty:
        raise ConflictError(
            f"В интервале {key} недостаточно мест: осталось {rest}, в заказе {qty}. Выберите другое время.",
            code="slot_full", details={"remaining": rest},
        )
    conn.execute("UPDATE slot_limits SET used = used + ? WHERE day = ? AND start = ?",
                 (qty, day.isoformat(), key))


def release(conn, day: str, key: str, qty: int) -> None:
    conn.execute("UPDATE slot_limits SET used = MAX(0, used - ?) WHERE day = ? AND start = ?",
                 (qty, day, key))
