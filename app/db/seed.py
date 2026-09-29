"""Демонстрационный набор (меню, цены, рекомендации — учебные, не предложения бренда)."""
from __future__ import annotations

import json

from app.db.database import Database
from app.db.schema import DATA_TABLES

POINT = {
    "id": "demo",
    "name": "Skuratov Coffee · учебная демо-точка",
    "address": "Учебный адрес: г. Москва, ул. Демонстрационная, 1",
}

# id, название, цена (коп.)
ADDONS = [
    ("vanilla", "Сироп ваниль", 4000),
    ("caramel", "Сироп солёная карамель", 4000),
    ("oat", "Овсяное молоко", 6000),
    ("coconut", "Кокосовое молоко", 6000),
    ("shot", "Дополнительный шот", 5000),
    ("cinnamon", "Корица", 1000),
]

MILK = ["vanilla", "caramel", "oat", "coconut", "shot", "cinnamon"]

# id, название, описание вкуса, размеры, добавки, учебная рекомендация
DRINKS = [
    ("espresso", "Эспрессо", "Плотный, с нотами тёмного шоколада и ореха",
     {"S": 15000}, ["shot"], ""),
    ("americano", "Американо", "Чистый вкус зерна, мягкая горчинка",
     {"S": 18000, "M": 21000, "L": 24000}, ["shot", "vanilla", "caramel"], ""),
    ("cappuccino", "Капучино", "Баланс эспрессо и плотной молочной пены",
     {"S": 22000, "M": 26000, "L": 30000}, MILK,
     "Учебная рекомендация: с корицей получается уютный осенний вкус"),
    ("latte", "Латте", "Много молока, нежный и сливочный",
     {"S": 23000, "M": 27000, "L": 31000}, MILK,
     "Учебная рекомендация: на овсяном молоке вкус становится ореховым"),
    ("flat_white", "Флэт уайт", "Двойной эспрессо и тонкий слой молока",
     {"S": 26000}, ["oat", "coconut", "shot"], ""),
    ("raf", "Раф", "Сливочный, сладкий, с бархатной текстурой",
     {"M": 32000, "L": 36000}, ["vanilla", "caramel", "cinnamon"],
     "Учебная рекомендация: с солёной карамелью — десерт в стакане"),
    ("cocoa", "Какао", "Горячий шоколадный напиток без кофеина",
     {"M": 25000, "L": 29000}, ["vanilla", "caramel", "oat", "coconut", "cinnamon"], ""),
    ("tea", "Чай облепиховый", "Ягодный, согревающий, с мёдом",
     {"M": 18000, "L": 21000}, ["cinnamon"], ""),
]


def _seed(conn) -> None:
    conn.execute("INSERT INTO point (id, name, address, paused) VALUES (?, ?, ?, 0)",
                 (POINT["id"], POINT["name"], POINT["address"]))
    for sort, (aid, name, price) in enumerate(ADDONS):
        conn.execute("INSERT INTO addons (id, name, price, available, sort) VALUES (?, ?, ?, 1, ?)",
                     (aid, name, price, sort))
    for sort, (did, name, desc, sizes, addons, rec) in enumerate(DRINKS):
        conn.execute(
            "INSERT INTO drinks (id, name, description, sizes_json, addon_ids_json, available,"
            " recommendation, sort) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
            (did, name, desc, json.dumps(sizes), json.dumps(addons), rec, sort),
        )


def reset_demo(db: Database) -> None:
    """Полный сброс к начальному набору. Только для автора (CLI), не публичный."""
    with db.transaction() as conn:
        for table in DATA_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'events'")
        _seed(conn)


def ensure_demo(db: Database) -> None:
    with db.transaction() as conn:
        if conn.execute("SELECT 1 FROM point").fetchone() is None:
            _seed(conn)
