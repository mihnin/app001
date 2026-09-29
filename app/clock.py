"""Единый серверный источник времени. Часы устройства гостя не используются."""
from __future__ import annotations

import time as _time
from datetime import datetime, timedelta, timezone


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """Управляемое время для тестов."""

    def __init__(self, start: datetime):
        self._now = start.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def set(self, value: datetime) -> None:
        self._now = value.astimezone(timezone.utc)

    def advance(self, **delta) -> None:
        self._now += timedelta(**delta)


class OffsetClock:
    """Тестовое время для демонстрации: стартует с заданного момента и идёт дальше."""

    def __init__(self, start: datetime):
        self._start = start.astimezone(timezone.utc)
        self._origin = _time.monotonic()

    def now(self) -> datetime:
        return self._start + timedelta(seconds=_time.monotonic() - self._origin)
