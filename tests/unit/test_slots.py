from datetime import date

from app.domain.slots import (
    acceptance_block_reason, bookable, day_grid, find_slot, local_day, remaining,
)
from tests.factories import PROFILE, msk

DAY = date(2026, 9, 29)


def test_grid_anchored_to_opening():
    grid = day_grid(DAY, PROFILE)
    assert len(grid) == 48                      # 12 часов × 4
    assert grid[0].key == "09:00"
    assert grid[-1].key == "20:45"
    assert grid[-1].end.hour == 21 and grid[-1].end.minute == 0


def test_find_slot():
    assert find_slot(DAY, "10:15", PROFILE).key == "10:15"
    assert find_slot(DAY, "10:10", PROFILE) is None
    assert find_slot(DAY, "garbage", PROFILE) is None


def test_lead_time():
    now = msk(10, 0)
    assert not bookable(find_slot(DAY, "10:00", PROFILE), now, PROFILE)
    assert bookable(find_slot(DAY, "10:15", PROFILE), now, PROFILE)   # ровно +15 минут
    assert not bookable(find_slot(DAY, "10:15", PROFILE), msk(10, 1), PROFILE)


def test_last_slot_and_other_day():
    assert bookable(find_slot(DAY, "20:45", PROFILE), msk(20, 30), PROFILE)
    assert not bookable(find_slot(DAY, "20:45", PROFILE), msk(20, 31), PROFILE)
    tomorrow = find_slot(date(2026, 9, 30), "10:00", PROFILE)
    assert not bookable(tomorrow, msk(9, 0), PROFILE)


def test_acceptance_hours():
    assert acceptance_block_reason(msk(8, 59), PROFILE, paused=False)
    assert acceptance_block_reason(msk(9, 0), PROFILE, paused=False) is None
    assert acceptance_block_reason(msk(20, 59), PROFILE, paused=False) is None
    assert "закры" in acceptance_block_reason(msk(21, 0), PROFILE, paused=False)
    assert "приостановлен" in acceptance_block_reason(msk(12, 0), PROFILE, paused=True)


def test_local_day_uses_point_timezone():
    # 23:30 UTC 28.09 = 02:30 МСК 29.09
    from datetime import datetime, timezone
    assert local_day(datetime(2026, 9, 28, 23, 30, tzinfo=timezone.utc), PROFILE) == DAY


def test_remaining_never_negative():
    assert remaining(6, 2) == 4
    assert remaining(1, 3) == 0
