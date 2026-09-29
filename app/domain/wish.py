"""Пожелание гостя (ФТ-04). Длина — в кодовых точках Unicode, перевод строки = 1 символ."""
from __future__ import annotations

from app.domain.errors import ValidationError


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def wish_length(text: str) -> int:
    return len(_normalize_newlines(text))


def normalize_wish(text, max_len: int) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        raise ValidationError("Пожелание должно быть текстом")
    text = _normalize_newlines(text)
    if not text.strip():
        return ""
    if len(text) > max_len:
        raise ValidationError(
            f"Пожелание длиннее {max_len} символов ({len(text)}). Сократите текст — мы его не обрезаем.",
            code="wish_too_long",
        )
    return text
