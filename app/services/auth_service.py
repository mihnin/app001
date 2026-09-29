"""Гостевой доступ и защищённая сессия сотрудника (ФТ-01). В БД хранятся только хэши токенов."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from app.services.context import Context


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def staff_login(ctx: Context, password, expected: str) -> str | None:
    if not isinstance(password, str) or not hmac.compare_digest(password.encode(), expected.encode()):
        return None
    token = new_token()
    with ctx.db.transaction() as conn:
        conn.execute("INSERT INTO staff_sessions (token_hash, created_at) VALUES (?, ?)",
                     (token_hash(token), ctx.now_iso()))
    return token


def is_staff(ctx: Context, token: str | None) -> bool:
    if not token:
        return False
    with ctx.db.read() as conn:
        row = conn.execute("SELECT 1 FROM staff_sessions WHERE token_hash = ?", (token_hash(token),)).fetchone()
    return row is not None


def staff_logout(ctx: Context, token: str | None) -> None:
    if not token:
        return
    with ctx.db.transaction() as conn:
        conn.execute("DELETE FROM staff_sessions WHERE token_hash = ?", (token_hash(token),))
