"""Дневная сводка по демонстрационным заказам (ФТ-15)."""
from __future__ import annotations

from datetime import date

from app.domain.slots import local_day
from app.domain.statuses import Status
from app.domain.summary import OrderFacts, compute_summary
from app.services.context import Context
from app.services.orders_repo import parse_ts


def daily_summary(ctx: Context, day: date | None = None) -> dict:
    day = day or local_day(ctx.clock.now(), ctx.profile)
    with ctx.db.read() as conn:
        rows = conn.execute("SELECT * FROM orders WHERE day = ? ORDER BY number", (day.isoformat(),)).fetchall()
    facts = [
        OrderFacts(
            id=r["id"], number=r["number"], status=Status(r["status"]),
            slot_end=parse_ts(r["slot_end"]), accepted_at=parse_ts(r["accepted_at"]),
            ready_at=parse_ts(r["ready_at"]), cancel_reason=r["cancel_reason"],
        )
        for r in rows
    ]
    summary = compute_summary(facts, ctx.clock.now())
    summary["day"] = day.isoformat()
    summary["demo_total"] = sum(r["total"] for r in rows)
    summary["note"] = "Сумма учебных заказов не является фактической выручкой."
    return summary
