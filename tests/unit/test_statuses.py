import pytest

from app.domain.errors import ValidationError
from app.domain.statuses import (
    FINAL, Status, can_advance, can_guest_cancel, can_staff_cancel,
    next_status, parse_status, releases_capacity,
)


def test_forward_path_only():
    assert next_status(Status.ACCEPTED) == Status.PREPARING
    assert next_status(Status.PREPARING) == Status.READY
    assert next_status(Status.READY) == Status.ISSUED
    assert next_status(Status.ISSUED) is None


@pytest.mark.parametrize("cur,target,ok", [
    (Status.ACCEPTED, Status.PREPARING, True),
    (Status.ACCEPTED, Status.READY, False),       # пропуск этапа
    (Status.READY, Status.PREPARING, False),      # возврат
    (Status.ISSUED, Status.READY, False),         # конечный
    (Status.CANCELLED, Status.PREPARING, False),
])
def test_can_advance(cur, target, ok):
    assert can_advance(cur, target) is ok


def test_final_statuses():
    assert FINAL == {Status.ISSUED, Status.CANCELLED, Status.NOT_RECEIVED}


def test_cancel_rights():
    assert can_guest_cancel(Status.ACCEPTED)
    assert not can_guest_cancel(Status.PREPARING)
    for s in (Status.ACCEPTED, Status.PREPARING, Status.READY):
        assert can_staff_cancel(s)
    for s in FINAL:
        assert not can_staff_cancel(s)


def test_capacity_released_only_before_preparing():
    assert releases_capacity(Status.ACCEPTED)
    assert not releases_capacity(Status.PREPARING)
    assert not releases_capacity(Status.READY)


def test_parse_status():
    assert parse_status("ready") == Status.READY
    with pytest.raises(ValidationError):
        parse_status("done")


def test_russian_labels():
    assert Status.ACCEPTED.label == "Принят"
    assert Status.NOT_RECEIVED.label == "Не получен"
