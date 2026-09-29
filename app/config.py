"""Настройки демонстрации и учебный профиль приёма (раздел 4.1 ТЗ)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Profile:
    tz_name: str = "Europe/Moscow"
    open_time: time = time(9, 0)
    close_time: time = time(21, 0)
    slot_minutes: int = 15
    lead_minutes: int = 15
    default_limit: int = 6
    min_drinks: int = 1
    max_drinks: int = 4
    wish_max: int = 200

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)


@dataclass(frozen=True)
class Settings:
    db_path: str = "data/app.db"
    staff_password: str = "barista"
    profile: Profile = field(default_factory=Profile)
    start_now: datetime | None = None   # тестовое время (aware)


def load_settings(env: dict | None = None) -> Settings:
    env = os.environ if env is None else env
    profile = Profile(tz_name=env.get("APP_TZ", "Europe/Moscow"))
    start_now = None
    if env.get("APP_NOW"):
        start_now = datetime.fromisoformat(env["APP_NOW"])
        if start_now.tzinfo is None:
            start_now = start_now.replace(tzinfo=profile.tz)
    return Settings(
        db_path=env.get("APP_DB", "data/app.db"),
        staff_password=env.get("STAFF_PASSWORD", "barista"),
        profile=profile,
        start_now=start_now,
    )
