"""Контекст сервисов: хранилище, часы, профиль."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.config import Profile
from app.db.database import Database


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass
class Context:
    db: Database
    clock: Clock
    profile: Profile

    def now_iso(self) -> str:
        return self.clock.now().isoformat()
