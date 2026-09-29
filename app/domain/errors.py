"""Различимые результаты операций (ФТ-16)."""
from __future__ import annotations


class DomainError(Exception):
    kind = "error"

    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.kind
        self.details = details or {}


class ValidationError(DomainError):
    kind = "validation"


class ForbiddenError(DomainError):
    kind = "forbidden"


class NotFoundError(DomainError):
    kind = "not_found"


class ConflictError(DomainError):
    """Конфликт состояния или бизнес-отказ (интервал заполнен, условия изменились)."""
    kind = "conflict"


class UnavailableError(DomainError):
    kind = "unavailable"
