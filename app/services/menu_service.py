"""Меню, точка, стоп-лист и пауза (ФТ-02, ФТ-11), проверка корзины для повтора (ФТ-12)."""
from __future__ import annotations

import json

from app.domain.cart import cart_total, line_problem, parse_cart, price_lines, total_quantity
from app.domain.errors import NotFoundError, ValidationError
from app.domain.menu import Addon, Drink, Menu
from app.domain.slots import acceptance_block_reason
from app.services.context import Context


def load_menu(conn) -> Menu:
    addons = {
        r["id"]: Addon(r["id"], r["name"], r["price"], bool(r["available"]))
        for r in conn.execute("SELECT * FROM addons ORDER BY sort, id")
    }
    drinks = {
        r["id"]: Drink(
            r["id"], r["name"], r["description"], json.loads(r["sizes_json"]),
            tuple(json.loads(r["addon_ids_json"])), bool(r["available"]), r["recommendation"],
        )
        for r in conn.execute("SELECT * FROM drinks ORDER BY sort, id")
    }
    return Menu(drinks=drinks, addons=addons)


def load_point(conn) -> dict:
    row = conn.execute("SELECT * FROM point LIMIT 1").fetchone()
    if row is None:
        raise NotFoundError("Демонстрационная точка не настроена")
    return {"id": row["id"], "name": row["name"], "address": row["address"], "paused": bool(row["paused"])}


def get_menu(ctx: Context) -> dict:
    with ctx.db.read() as conn:
        return load_menu(conn).to_dict()


def get_point(ctx: Context) -> dict:
    with ctx.db.read() as conn:
        point = load_point(conn)
    p = ctx.profile
    point.update({
        "timezone": p.tz_name,
        "open": p.open_time.strftime("%H:%M"),
        "close": p.close_time.strftime("%H:%M"),
        "now": ctx.clock.now().astimezone(p.tz).isoformat(),
        "block_reason": acceptance_block_reason(ctx.clock.now(), p, point["paused"]),
        "rules": {
            "min_drinks": p.min_drinks, "max_drinks": p.max_drinks,
            "wish_max": p.wish_max, "slot_minutes": p.slot_minutes, "lead_minutes": p.lead_minutes,
        },
        "notice": "Учебный проект. Меню, цены, адрес и рекомендации демонстрационные; "
                  "реальные заказы и оплата не создаются. Уточнить детали можно у сотрудника при получении.",
    })
    return point


def _set_flag(ctx: Context, table: str, item_id: str, available) -> None:
    if not isinstance(available, bool):
        raise ValidationError("Признак доступности должен быть true или false")
    with ctx.db.transaction() as conn:
        cur = conn.execute(f"UPDATE {table} SET available = ? WHERE id = ?", (int(available), item_id))
        if cur.rowcount == 0:
            raise NotFoundError("Позиция меню не найдена")


def set_drink_available(ctx: Context, drink_id: str, available: bool) -> None:
    _set_flag(ctx, "drinks", drink_id, available)


def set_addon_available(ctx: Context, addon_id: str, available: bool) -> None:
    _set_flag(ctx, "addons", addon_id, available)


def set_paused(ctx: Context, paused: bool) -> None:
    if not isinstance(paused, bool):
        raise ValidationError("Признак паузы должен быть true или false")
    with ctx.db.transaction() as conn:
        conn.execute("UPDATE point SET paused = ?", (int(paused),))


def check_cart(ctx: Context, raw_items) -> dict:
    """Проверка корзины по текущему меню без исключений по позициям (повтор избранного)."""
    lines = parse_cart(raw_items)
    with ctx.db.read() as conn:
        menu = load_menu(conn)
    result, priced_ok = [], []
    for line in lines:
        problem = line_problem(line, menu)
        entry = {"drink_id": line.drink_id, "size": line.size, "addons": list(line.addon_ids),
                 "qty": line.qty, "problem": problem}
        if problem is None:
            priced = price_lines([line], menu)[0]
            priced_ok.append(priced)
            entry.update(priced.to_dict())
        result.append(entry)
    qty = total_quantity(lines)
    qty_problem = None
    if not lines:
        qty_problem = "Корзина пуста"
    elif qty > ctx.profile.max_drinks:
        qty_problem = f"В заказе может быть не больше {ctx.profile.max_drinks} напитков"
    return {
        "lines": result,
        "total": cart_total(priced_ok),
        "quantity_problem": qty_problem,
        "ok": qty_problem is None and all(e["problem"] is None for e in result),
    }
