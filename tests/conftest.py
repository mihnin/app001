import uuid

import pytest

from app.clock import FixedClock
from app.config import Profile
from app.db.database import Database
from app.db.seed import reset_demo
from app.services.context import Context
from tests.factories import msk

GUEST_A = "a" * 64
GUEST_B = "b" * 64


@pytest.fixture
def clock():
    return FixedClock(msk(10, 0))


@pytest.fixture
def ctx(tmp_path, clock):
    db = Database(str(tmp_path / "test.db"))
    reset_demo(db)
    return Context(db=db, clock=clock, profile=Profile())


def new_attempt() -> str:
    return str(uuid.uuid4())


LATTE_M_OAT = {"drink_id": "latte", "size": "M", "addons": ["oat"], "qty": 1}   # 270 + 60 = 330 ₽
LATTE_M_OAT_PRICE = 33000
