"""Модель меню: напитки, размеры, добавки и их совместимость. Цены — в копейках."""
from __future__ import annotations

from dataclasses import dataclass, field

SIZE_LABELS = {"S": "S · 250 мл", "M": "M · 350 мл", "L": "L · 450 мл"}


@dataclass(frozen=True)
class Addon:
    id: str
    name: str
    price: int
    available: bool = True


@dataclass(frozen=True)
class Drink:
    id: str
    name: str
    description: str
    sizes: dict[str, int]
    addon_ids: tuple[str, ...] = ()
    available: bool = True
    recommendation: str = ""


@dataclass(frozen=True)
class Menu:
    drinks: dict[str, Drink] = field(default_factory=dict)
    addons: dict[str, Addon] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "drinks": [
                {
                    "id": d.id, "name": d.name, "description": d.description,
                    "sizes": [{"code": c, "label": SIZE_LABELS.get(c, c), "price": p}
                              for c, p in d.sizes.items()],
                    "addon_ids": list(d.addon_ids),
                    "available": d.available,
                    "recommendation": d.recommendation,
                }
                for d in self.drinks.values()
            ],
            "addons": [
                {"id": a.id, "name": a.name, "price": a.price, "available": a.available}
                for a in self.addons.values()
            ],
        }
