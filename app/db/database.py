"""Доступ к SQLite. Запись — только в транзакции BEGIN IMMEDIATE (сериализует приём заказов)."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.db.schema import SCHEMA
from app.domain.errors import UnavailableError


class Database:
    def __init__(self, path: str):
        self.path = path
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Атомарная операция: всё или ничего. Сбой хранилища → UnavailableError."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            raise UnavailableError(
                "Хранилище временно недоступно, операция не выполнена. Повторите попытку.",
                details={"reason": str(exc)},
            ) from exc
        finally:
            conn.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        except sqlite3.Error as exc:
            raise UnavailableError("Хранилище временно недоступно. Повторите попытку.") from exc
        finally:
            conn.close()
