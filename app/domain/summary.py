"""Дневная сводка (ФТ-15). Чистые функции над фактами заказов."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from app.domain.statuses import ACTIVE, LABELS, Status


@dataclass(frozen=True)
class OrderFacts:
    id: str
    number: str
    status: Status
    slot_end: datetime
    accepted_at: datetime
    ready_at: datetime | None
    cancel_reason: str | None


def readiness_ratio(rows: list[OrderFacts]) -> float | None:
    """Готовность к концу интервала = готовые не позже конца окна / все достигшие готовности."""
    reached = [r for r in rows if r.ready_at is not None]
    if not reached:
        return None
    on_time = sum(1 for r in reached if r.ready_at <= r.slot_end)
    return on_time / len(reached)


def compute_summary(rows: list[OrderFacts], now: datetime) -> dict:
    by_status = {label: 0 for label in LABELS.values()}
    for r in rows:
        by_status[r.status.label] += 1
    durations = [
        {"number": r.number, "seconds": int((r.ready_at - r.accepted_at).total_seconds())}
        for r in rows if r.ready_at is not None
    ]
    ratio = readiness_ratio(rows)
    return {
        "total": len(rows),
        "by_status": by_status,
        "cancel_reasons": dict(Counter(r.cancel_reason for r in rows if r.status == Status.CANCELLED)),
        "durations": durations,
        "avg_ready_seconds": (
            round(sum(d["seconds"] for d in durations) / len(durations)) if durations else None
        ),
        "readiness": {
            "ratio": ratio,
            "text": "Нет данных" if ratio is None else f"{round(ratio * 100)}%",
        },
        "overdue_active": [r.number for r in rows if r.status in ACTIVE and r.slot_end < now],
        "not_received": [r.number for r in rows if r.status == Status.NOT_RECEIVED],
    }
