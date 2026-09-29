"""Интервалы получения (ФТ-05). Сетка привязана к открытию точки."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.config import Profile

_KEY_RE = re.compile(r"^\d{2}:\d{2}$")


@dataclass(frozen=True)
class Slot:
    start: datetime   # aware, местное время точки
    end: datetime

    @property
    def key(self) -> str:
        return self.start.strftime("%H:%M")


def local_now(now_utc: datetime, profile: Profile) -> datetime:
    return now_utc.astimezone(profile.tz)


def local_day(now_utc: datetime, profile: Profile) -> date:
    return local_now(now_utc, profile).date()


def day_grid(day: date, profile: Profile) -> list[Slot]:
    start = datetime.combine(day, profile.open_time, tzinfo=profile.tz)
    close = datetime.combine(day, profile.close_time, tzinfo=profile.tz)
    step = timedelta(minutes=profile.slot_minutes)
    grid = []
    while start + step <= close:
        grid.append(Slot(start, start + step))
        start += step
    return grid


def find_slot(day: date, key: str, profile: Profile) -> Slot | None:
    if not isinstance(key, str) or not _KEY_RE.match(key):
        return None
    for slot in day_grid(day, profile):
        if slot.key == key:
            return slot
    return None


def bookable(slot: Slot, now_utc: datetime, profile: Profile) -> bool:
    """Время интервала допустимо: сегодня, не раньше now+упреждение, конец не позже закрытия."""
    now = local_now(now_utc, profile)
    if slot.start.date() != now.date():
        return False
    close = datetime.combine(now.date(), profile.close_time, tzinfo=profile.tz)
    return slot.start >= now + timedelta(minutes=profile.lead_minutes) and slot.end <= close


def acceptance_block_reason(now_utc: datetime, profile: Profile, paused: bool) -> str | None:
    now = local_now(now_utc, profile)
    opening = profile.open_time.strftime("%H:%M")
    closing = profile.close_time.strftime("%H:%M")
    if now.time() < profile.open_time:
        return f"Приём заказов откроется в {opening}"
    if now.time() >= profile.close_time:
        return f"Точка закрыта: приём заказов до {closing}"
    if paused:
        return "Приём новых заказов временно приостановлен"
    return None


def remaining(limit: int, used: int) -> int:
    return max(0, limit - used)
