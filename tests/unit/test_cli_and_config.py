from datetime import datetime

from app import cli
from app.clock import OffsetClock
from app.config import load_settings
from app.db.database import Database
from app.services import menu_service
from app.services.context import Context


def test_load_settings_with_test_time():
    s = load_settings({"APP_NOW": "2026-09-29T10:00", "STAFF_PASSWORD": "x", "APP_DB": "d.db"})
    assert s.start_now.utcoffset().total_seconds() == 3 * 3600
    assert s.staff_password == "x" and s.db_path == "d.db"
    assert load_settings({}).start_now is None


def test_offset_clock_moves_forward():
    start = datetime.fromisoformat("2026-09-29T10:00+03:00")
    clock = OffsetClock(start)
    assert clock.now() >= start


def test_reset_requires_confirmation(tmp_path, monkeypatch, capsys):
    db_path = str(tmp_path / "cli.db")
    monkeypatch.setenv("APP_DB", db_path)
    assert cli.main(["reset"]) == 2
    assert cli.main(["reset", "--yes"]) == 0
    ctx = Context(db=Database(db_path), clock=OffsetClock(datetime.now().astimezone()),
                  profile=load_settings().profile)
    assert len(menu_service.get_menu(ctx)["drinks"]) == 8
