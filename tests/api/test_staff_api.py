"""Панель сотрудника через HTTP: ПИ-01, 05, 07, 08, 09, 11, 12."""
import uuid

from fastapi.testclient import TestClient

from tests.factories import msk

ESPRESSO = {"drink_id": "espresso", "size": "S", "addons": [], "qty": 1}


def place(client, slot="10:30", qty=1):
    body = {"attempt_id": str(uuid.uuid4()), "items": [{**ESPRESSO, "qty": qty}], "wish": "",
            "slot": slot, "expected_total": 15000 * qty}
    r = client.post("/api/orders", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_staff_routes_require_login(guest, app):
    for method, url in [("get", "/api/staff/queue"), ("post", "/api/staff/pause"),
                        ("get", "/api/staff/summary"), ("post", "/api/staff/close-day")]:
        r = getattr(guest, method)(url, **({"json": {}} if method == "post" else {}))
        assert r.status_code == 403, url
        assert r.json()["error"]["kind"] == "forbidden"
    bad = TestClient(app).post("/api/staff/login", json={"password": "nope"})
    assert bad.status_code == 403


def test_logout_ends_session(staff):
    assert staff.get("/api/staff/me").json() == {"staff": True}
    staff.post("/api/staff/logout")
    assert staff.get("/api/staff/queue").status_code == 403
    assert staff.get("/api/staff/me").json() == {"staff": False}


def test_status_path_and_stale_command(guest, staff):
    card = place(guest)
    url = f"/api/staff/orders/{card['id']}/advance"
    assert staff.post(url, json={"expected_status": "accepted"}).json()["status"] == "preparing"
    stale = staff.post(url, json={"expected_status": "accepted"})
    assert stale.status_code == 409 and stale.json()["error"]["details"]["order"]["status"] == "preparing"
    assert staff.post(url, json={"expected_status": "preparing"}).json()["status"] == "ready"
    assert guest.get(f"/api/orders/{card['id']}").json()["status_label"] == "Готов"
    assert staff.post(url, json={"expected_status": "ready"}).json()["status"] == "issued"
    assert staff.post(url, json={"expected_status": "issued"}).status_code == 409
    assert staff.post(url, json={"expected_status": "bogus"}).status_code == 422


def test_staff_cancel_with_reason_visible_to_guest(guest, staff):
    card = place(guest)
    url = f"/api/staff/orders/{card['id']}/cancel"
    assert staff.post(url, json={"expected_status": "accepted", "reason": ""}).status_code == 422
    r = staff.post(url, json={"expected_status": "accepted", "reason": "Пожелание меняет состав, оформите новый"})
    assert r.status_code == 200
    g = guest.get(f"/api/orders/{card['id']}").json()
    assert g["status_label"] == "Отменён" and g["cancel_reason"].startswith("Пожелание")


def test_pause_stop_list_limits(guest, guest2, staff):
    place(guest)
    assert staff.post("/api/staff/pause", json={"paused": True}).status_code == 200
    body = {"attempt_id": str(uuid.uuid4()), "items": [ESPRESSO], "wish": "", "slot": "10:30",
            "expected_total": 15000}
    r = guest.post("/api/orders", json=body)
    assert r.status_code == 409 and r.json()["error"]["code"] == "acceptance_closed"
    assert len(guest.get("/api/orders").json()) == 1          # принятые сохранены
    staff.post("/api/staff/pause", json={"paused": False})
    staff.post("/api/staff/drinks/espresso/availability", json={"available": False})
    assert guest.post("/api/orders", json=body).json()["error"]["code"] == "item_unavailable"
    staff.post("/api/staff/drinks/espresso/availability", json={"available": True})
    assert staff.post("/api/staff/slots/10:30/limit", json={"limit": -1}).status_code == 422
    assert staff.post("/api/staff/slots/10:30/limit", json={"limit": 2}).json()["remaining"] == 1
    place(guest2)
    r = guest.post("/api/orders", json={**body, "attempt_id": str(uuid.uuid4())})
    assert r.json()["error"]["code"] == "slot_full"
    slots = {s["key"]: s for s in staff.get("/api/staff/slots").json()["slots"]}
    assert slots["10:30"]["used"] == 2 and slots["10:30"]["limit"] == 2
    menu = staff.get("/api/staff/menu").json()
    assert any(d["id"] == "espresso" and d["available"] for d in menu["drinks"])


def test_close_day_and_summary(guest, staff, clock):
    a, b = place(guest), place(guest)
    staff.post(f"/api/staff/orders/{b['id']}/advance", json={"expected_status": "accepted"})
    staff.post(f"/api/staff/orders/{b['id']}/advance", json={"expected_status": "preparing"})
    assert staff.post("/api/staff/close-day").status_code == 409     # ещё открыто
    clock.set(msk(21, 1))
    assert staff.post("/api/staff/close-day").json() == {"cancelled": 1, "not_received": 1}
    assert staff.post("/api/staff/close-day").json() == {"cancelled": 0, "not_received": 0}
    s = staff.get("/api/staff/summary").json()
    assert s["total"] == 2 and s["not_received"] == [b["number"]]
    assert s["readiness"]["text"] == "100%"
    empty = staff.get("/api/staff/summary", params={"day": "2026-09-28"}).json()
    assert empty["total"] == 0 and empty["readiness"]["text"] == "Нет данных"
    assert staff.get("/api/staff/summary", params={"day": "garbage"}).status_code == 422


def test_no_public_reset_endpoint(guest, staff):
    for client in (guest, staff):
        assert client.post("/api/reset").status_code in (404, 405)
        assert client.post("/api/staff/reset").status_code in (404, 405)
