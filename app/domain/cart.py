"""Корзина: разбор, проверка совместимости и расчёт стоимости (ФТ-03)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.config import Profile
from app.domain.errors import ConflictError, ValidationError
from app.domain.menu import Menu


@dataclass(frozen=True)
class CartLine:
    drink_id: str
    size: str
    addon_ids: tuple[str, ...]
    qty: int


@dataclass(frozen=True)
class PricedAddon:
    id: str
    name: str
    price: int


@dataclass(frozen=True)
class PricedLine:
    drink_id: str
    drink_name: str
    size: str
    addons: tuple[PricedAddon, ...]
    unit_price: int
    qty: int
    line_total: int

    def to_dict(self) -> dict:
        return {
            "drink_id": self.drink_id, "drink_name": self.drink_name, "size": self.size,
            "addons": [{"id": a.id, "name": a.name, "price": a.price} for a in self.addons],
            "unit_price": self.unit_price, "qty": self.qty, "line_total": self.line_total,
        }


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_cart(raw) -> list[CartLine]:
    if not isinstance(raw, list):
        raise ValidationError("Корзина должна быть списком позиций")
    lines = []
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValidationError(f"Позиция {i}: неверный формат")
        drink_id, size = item.get("drink_id"), item.get("size")
        addons, qty = item.get("addons", []), item.get("qty")
        if not isinstance(drink_id, str) or not drink_id:
            raise ValidationError(f"Позиция {i}: не указан напиток")
        if not isinstance(size, str) or not size:
            raise ValidationError(f"Позиция {i}: не указан размер")
        if not isinstance(addons, list) or not all(isinstance(a, str) and a for a in addons):
            raise ValidationError(f"Позиция {i}: неверный список добавок")
        if len(set(addons)) != len(addons):
            raise ValidationError(f"Позиция {i}: добавка указана дважды")
        if not _is_int(qty) or qty <= 0:
            raise ValidationError(f"Позиция {i}: количество должно быть положительным целым числом")
        lines.append(CartLine(drink_id, size, tuple(addons), qty))
    return lines


def total_quantity(lines: list[CartLine]) -> int:
    return sum(line.qty for line in lines)


def check_quantity(lines: list[CartLine], profile: Profile) -> None:
    if not lines:
        raise ValidationError("Корзина пуста")
    total = total_quantity(lines)
    if total < profile.min_drinks or total > profile.max_drinks:
        raise ValidationError(
            f"В заказе может быть от {profile.min_drinks} до {profile.max_drinks} напитков, сейчас {total}"
        )


def _structural_problem(line: CartLine, menu: Menu) -> str | None:
    drink = menu.drinks.get(line.drink_id)
    if drink is None:
        return f"Напиток «{line.drink_id}» отсутствует в меню"
    if line.size not in drink.sizes:
        return f"{drink.name}: размер {line.size} недоступен для этого напитка"
    for addon_id in line.addon_ids:
        if addon_id not in drink.addon_ids or addon_id not in menu.addons:
            return f"{drink.name}: добавка «{addon_id}» несовместима с напитком"
    return None


def _availability_problem(line: CartLine, menu: Menu) -> str | None:
    drink = menu.drinks[line.drink_id]
    if not drink.available:
        return f"{drink.name} сейчас недоступен"
    for addon_id in line.addon_ids:
        addon = menu.addons[addon_id]
        if not addon.available:
            return f"{drink.name}: добавка «{addon.name}» сейчас недоступна"
    return None


def line_problem(line: CartLine, menu: Menu) -> str | None:
    """Описание проблемы позиции без исключения — для проверки повтора избранного."""
    return _structural_problem(line, menu) or _availability_problem(line, menu)


def price_lines(lines: list[CartLine], menu: Menu) -> list[PricedLine]:
    for line in lines:
        problem = _structural_problem(line, menu)
        if problem:
            raise ValidationError(problem)
    for line in lines:
        problem = _availability_problem(line, menu)
        if problem:
            raise ConflictError(problem, code="item_unavailable")
    priced = []
    for line in lines:
        drink = menu.drinks[line.drink_id]
        addons = tuple(PricedAddon(a, menu.addons[a].name, menu.addons[a].price) for a in line.addon_ids)
        unit = drink.sizes[line.size] + sum(a.price for a in addons)
        priced.append(PricedLine(drink.id, drink.name, line.size, addons, unit, line.qty, unit * line.qty))
    return priced


def cart_total(priced: list[PricedLine]) -> int:
    return sum(p.line_total for p in priced)


def fingerprint(lines: list[CartLine], wish: str, slot_key: str) -> str:
    """Отпечаток подтверждённого содержимого попытки оформления (ФТ-07)."""
    payload = {
        "lines": [[l.drink_id, l.size, sorted(l.addon_ids), l.qty] for l in lines],
        "wish": wish,
        "slot": slot_key,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
