"""Эксплуатационные команды (роль автора проекта, не публичный интерфейс).

    python -m app.cli run [--host 127.0.0.1] [--port 8000]
    python -m app.cli reset --yes
"""
from __future__ import annotations

import argparse
import sys

from app.config import load_settings
from app.db.database import Database
from app.db.seed import reset_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="Skuratov Coffee — учебный предзаказ")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="запустить веб-сервер")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8000)
    reset = sub.add_parser("reset", help="сбросить демонстрацию к начальному набору")
    reset.add_argument("--yes", action="store_true", help="подтверждение сброса (обязательно)")
    args = parser.parse_args(argv)

    if args.cmd == "run":
        import uvicorn
        from app.main import create_app
        uvicorn.run(create_app(), host=args.host, port=args.port)
        return 0

    if not args.yes:
        print("Сброс удалит все заказы и настройки приёма. Повторите с флагом --yes.", file=sys.stderr)
        return 2
    settings = load_settings()
    reset_demo(Database(settings.db_path))
    print(f"Демонстрация сброшена: {settings.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
