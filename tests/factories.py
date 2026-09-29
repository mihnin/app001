"""Общие тестовые данные: небольшое меню и профиль."""
from datetime import datetime, timezone

from app.config import Profile
from app.domain.menu import Addon, Drink, Menu

PROFILE = Profile()


def make_menu(**overrides) -> Menu:
    addons = {
        "syrup": Addon("syrup", "Сироп ваниль", 4000),
        "oat": Addon("oat", "Овсяное молоко", 6050),
        "shot": Addon("shot", "Доп. шот", 5000),
    }
    drinks = {
        "espresso": Drink("espresso", "Эспрессо", "Плотный", {"S": 15000}, ("shot",)),
        "latte": Drink("latte", "Латте", "Мягкий", {"S": 20000, "M": 25000, "L": 29900},
                       ("syrup", "oat", "shot")),
        "cocoa": Drink("cocoa", "Какао", "Сладкий", {"M": 22000}, ("syrup",)),
    }
    for key, value in overrides.items():
        if key in drinks:
            drinks[key] = value
        else:
            addons[key] = value
    return Menu(drinks=drinks, addons=addons)


def msk(hh: int, mm: int = 0, day: int = 29) -> datetime:
    """Местное время точки (МСК) → aware UTC."""
    return datetime(2026, 9, day, hh, mm, tzinfo=PROFILE.tz).astimezone(timezone.utc)
