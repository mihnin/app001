"""Зависимости: контекст, гостевой доступ по cookie, проверка сотрудника."""
from __future__ import annotations

from datetime import date

from fastapi import Request, Response

from app.domain.errors import ForbiddenError, ValidationError
from app.services import auth_service
from app.services.context import Context

GUEST_COOKIE = "guest_token"
STAFF_COOKIE = "staff_token"
GUEST_MAX_AGE = 180 * 24 * 3600


def get_ctx(request: Request) -> Context:
    return request.app.state.ctx


def guest_id(request: Request, response: Response) -> str:
    """Хэш гостевого токена. Новый гость получает случайный токен в HttpOnly cookie."""
    token = request.cookies.get(GUEST_COOKIE)
    if not token or len(token) < 20 or len(token) > 128:
        token = auth_service.new_token()
        response.set_cookie(GUEST_COOKIE, token, max_age=GUEST_MAX_AGE, httponly=True, samesite="lax")
    return auth_service.token_hash(token)


def require_staff(request: Request) -> None:
    if not auth_service.is_staff(get_ctx(request), request.cookies.get(STAFF_COOKIE)):
        raise ForbiddenError("Требуется вход сотрудника", code="staff_required")


def parse_day(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError("Дата должна быть в формате ГГГГ-ММ-ДД") from None
