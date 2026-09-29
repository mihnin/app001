"""Статусы заказа и разрешённые переходы (ФТ-09, ФТ-10, ФТ-13)."""
from __future__ import annotations

from enum import StrEnum

from app.domain.errors import ValidationError


class Status(StrEnum):
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY = "ready"
    ISSUED = "issued"
    CANCELLED = "cancelled"
    NOT_RECEIVED = "not_received"

    @property
    def label(self) -> str:
        return LABELS[self]


LABELS = {
    Status.ACCEPTED: "Принят",
    Status.PREPARING: "Готовится",
    Status.READY: "Готов",
    Status.ISSUED: "Выдан",
    Status.CANCELLED: "Отменён",
    Status.NOT_RECEIVED: "Не получен",
}

FINAL = frozenset({Status.ISSUED, Status.CANCELLED, Status.NOT_RECEIVED})
ACTIVE = frozenset({Status.ACCEPTED, Status.PREPARING, Status.READY})

_FORWARD = {
    Status.ACCEPTED: Status.PREPARING,
    Status.PREPARING: Status.READY,
    Status.READY: Status.ISSUED,
}

GUEST_CANCEL_REASON = "Отменён гостем"
CLOSE_DAY_REASON = "Не выполнен до закрытия"


def next_status(current: Status) -> Status | None:
    return _FORWARD.get(current)


def can_advance(current: Status, target: Status) -> bool:
    return _FORWARD.get(current) == target


def can_guest_cancel(current: Status) -> bool:
    return current == Status.ACCEPTED


def can_staff_cancel(current: Status) -> bool:
    return current in ACTIVE


def releases_capacity(previous: Status) -> bool:
    """Ёмкость возвращается только при отмене до начала приготовления."""
    return previous == Status.ACCEPTED


def parse_status(value: str) -> Status:
    try:
        return Status(value)
    except ValueError:
        raise ValidationError(f"Неизвестный статус: {value!r}") from None
