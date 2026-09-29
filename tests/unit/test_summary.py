from app.domain.statuses import Status
from app.domain.summary import OrderFacts, compute_summary, readiness_ratio
from tests.factories import msk


def facts(num, status, slot_end, accepted, ready=None, reason=None):
    return OrderFacts(id=num, number=num, status=status, slot_end=slot_end,
                      accepted_at=accepted, ready_at=ready, cancel_reason=reason)


def test_empty_day():
    s = compute_summary([], now=msk(12))
    assert s["total"] == 0
    assert s["readiness"]["text"] == "Нет данных"
    assert s["readiness"]["ratio"] is None
    assert s["avg_ready_seconds"] is None


def test_readiness_ratio_counts_early_and_cancelled_after_ready():
    rows = [
        facts("001", Status.ISSUED, msk(10, 30), msk(10), ready=msk(10, 20)),        # вовремя
        facts("002", Status.ISSUED, msk(10, 30), msk(10), ready=msk(10, 30)),        # ровно в конец
        facts("003", Status.NOT_RECEIVED, msk(10, 30), msk(10), ready=msk(10, 31)),  # поздно
        facts("004", Status.CANCELLED, msk(11), msk(10), ready=msk(10, 5), reason="x"),  # отмена после готовности
        facts("005", Status.CANCELLED, msk(11), msk(10), reason="Отменён гостем"),   # не готов — вне знаменателя
    ]
    assert readiness_ratio(rows) == 3 / 4
    s = compute_summary(rows, now=msk(22))
    assert s["readiness"]["text"] == "75%"
    assert s["total"] == 5
    assert s["by_status"]["Выдан"] == 2
    assert s["cancel_reasons"] == {"x": 1, "Отменён гостем": 1}
    assert s["not_received"] == ["003"]


def test_zero_duration_differs_from_missing():
    rows = [facts("001", Status.READY, msk(10, 30), msk(10), ready=msk(10))]
    s = compute_summary(rows, now=msk(10, 10))
    assert s["durations"] == [{"number": "001", "seconds": 0}]
    assert s["avg_ready_seconds"] == 0


def test_overdue_active():
    rows = [
        facts("001", Status.PREPARING, msk(10, 30), msk(10)),
        facts("002", Status.ACCEPTED, msk(12), msk(10)),
        facts("003", Status.READY, msk(10, 15), msk(10), ready=msk(10, 10)),
    ]
    s = compute_summary(rows, now=msk(11))
    assert s["overdue_active"] == ["001", "003"]
