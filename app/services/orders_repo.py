"""Чтение заказов из БД и преобразование в карточку (одинаковую для гостя и сотрудника)."""
from __future__ import annotations

import json
from datetime import datetime

from app.domain.statuses import Status, can_guest_cancel


def _lines(conn, order_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM order_lines WHERE order_id = ? ORDER BY pos", (order_id,))
    return [
        {
            "drink_id": r["drink_id"], "drink_name": r["drink_name"], "size": r["size"],
            "addons": json.loads(r["addons_json"]), "unit_price": r["unit_price"],
            "qty": r["qty"], "line_total": r["line_total"],
        }
        for r in rows
    ]


def _events(conn, order_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM events WHERE order_id = ? ORDER BY id", (order_id,))
    return [
        {
            "prev_status": r["prev_status"], "new_status": r["new_status"],
            "new_label": Status(r["new_status"]).label,
            "at": r["at"], "actor": r["actor"], "reason": r["reason"],
        }
        for r in rows
    ]


def to_card(conn, row) -> dict:
    status = Status(row["status"])
    return {
        "id": row["id"],
        "number": row["number"],
        "day": row["day"],
        "status": status.value,
        "status_label": status.label,
        "point": {"name": row["point_name"], "address": row["point_address"]},
        "slot": {"key": row["slot_key"], "start": row["slot_start"], "end": row["slot_end"]},
        "lines": _lines(conn, row["id"]),
        "total": row["total"],
        "wish": row["wish"],
        "accepted_at": row["accepted_at"],
        "preparing_at": row["preparing_at"],
        "ready_at": row["ready_at"],
        "finished_at": row["finished_at"],
        "cancelled_by": row["cancelled_by"],
        "cancel_reason": row["cancel_reason"],
        "guest_can_cancel": can_guest_cancel(status),
        "events": _events(conn, row["id"]),
    }


def fetch_row(conn, order_id: str):
    return conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def fetch_card(conn, order_id: str) -> dict | None:
    row = fetch_row(conn, order_id)
    return to_card(conn, row) if row else None


def parse_ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def insert_event(conn, order_id: str, prev: str | None, new: str, at: str, actor: str,
                 reason: str | None = None) -> None:
    conn.execute(
        "INSERT INTO events (order_id, prev_status, new_status, at, actor, reason) VALUES (?, ?, ?, ?, ?, ?)",
        (order_id, prev, new, at, actor, reason),
    )


def order_qty(conn, order_id: str) -> int:
    return conn.execute("SELECT COALESCE(SUM(qty), 0) FROM order_lines WHERE order_id = ?",
                        (order_id,)).fetchone()[0]
