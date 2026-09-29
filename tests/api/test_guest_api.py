"""Гостевой путь через HTTP: ПИ-01, 02, 03, 04, 05, 06, 10, 12."""
import uuid

from tests.factories import msk

LATTE = {"drink_id": "latte", "size": "L", "addons": ["oat", "vanilla"], "qty": 2}  # (310+60+40)*2 = 820 ₽
LATTE_TOTAL = 82000


def order_body(**kw):
    body = {"attempt_id": str(uuid.uuid4()), "items": [LATTE], "wish": "", "slot": "10:30",
            "expected_total": LATTE_TOTAL}
    body.update(kw)
    return body


def test_index_pages_served_with_security_headers(guest):
    r = guest.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert guest.get("/staff").status_code == 200


def test_point_and_menu_are_marked_as_demo(guest):
    point = guest.get("/api/point").json()
    assert point["timezone"] == "Europe/Moscow" and point["open"] == "09:00"
    assert "Учебный" in point["notice"] and "Учебный адрес" in point["address"]
    menu = guest.get("/api/menu").json()
    assert 6 <= len(menu["drinks"]) <= 10
    recs = [d["recommendation"] for d in menu["drinks"] if d["recommendation"]]
    assert recs and all(r.startswith("Учебная рекомендация") for r in recs)


def test_guest_cookie_is_httponly(guest):
    r = guest.get("/api/orders")
    assert "httponly" in r.headers["set-cookie"].lower()


def test_place_and_view_order_matches_independent_total(guest, staff):
    r = guest.post("/api/orders", json=order_body(wish="<script>alert(1)</script> погорячее"))
    assert r.status_code == 201, r.text
    card = r.json()
    assert card["total"] == 82000 == sum(l["line_total"] for l in card["lines"])
    assert card["status_label"] == "Принят"
    staff_card = next(o for o in staff.get("/api/staff/queue").json() if o["id"] == card["id"])
    for key in ("lines", "total", "wish", "slot", "point", "number"):
        assert staff_card[key] == card[key]
    assert guest.get(f"/api/orders/{card['id']}").json()["wish"].startswith("<script>")


def test_double_submit_returns_same_order(guest):
    body = order_body()
    first = guest.post("/api/orders", json=body)
    second = guest.post("/api/orders", json=body)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(guest.get("/api/orders").json()) == 1
    assert guest.get(f"/api/attempts/{body['attempt_id']}").json()["id"] == first.json()["id"]
    assert guest.get(f"/api/attempts/{uuid.uuid4()}").status_code == 404


def test_error_kinds_are_distinguishable(guest):
    empty = guest.post("/api/orders", json=order_body(items=[]))
    assert empty.status_code == 422 and empty.json()["error"]["kind"] == "validation"
    changed = guest.post("/api/orders", json=order_body(expected_total=1))
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "conditions_changed"
    long_wish = guest.post("/api/orders", json=order_body(wish="x" * 201))
    assert long_wish.status_code == 422 and "200" in long_wish.json()["error"]["message"]
    bad_json = guest.post("/api/orders", content=b"not json", headers={"content-type": "application/json"})
    assert bad_json.status_code == 422
    assert guest.get("/api/orders").json() == []


def test_slots_endpoint(guest, clock):
    data = guest.get("/api/slots", params={"qty": 2}).json()
    by_key = {s["key"]: s for s in data["slots"]}
    assert not by_key["10:00"]["available"] and by_key["10:15"]["available"]
    clock.set(msk(21, 0))
    data = guest.get("/api/slots").json()
    assert data["block_reason"] and not any(s["available"] for s in data["slots"])


def test_foreign_order_is_not_accessible(guest, guest2):
    card = guest.post("/api/orders", json=order_body()).json()
    assert guest2.get(f"/api/orders/{card['id']}").status_code == 404
    assert guest2.post(f"/api/orders/{card['id']}/cancel").status_code == 404
    assert guest2.get("/api/orders").json() == []


def test_forged_cookie_gives_no_access(guest, app):
    from fastapi.testclient import TestClient
    card = guest.post("/api/orders", json=order_body()).json()
    intruder = TestClient(app, cookies={"guest_token": "forged-token-value-1234567890"})
    assert intruder.get(f"/api/orders/{card['id']}").status_code == 404


def test_guest_cancel_flow(guest, staff):
    card = guest.post("/api/orders", json=order_body()).json()
    r = guest.post(f"/api/orders/{card['id']}/cancel")
    assert r.status_code == 200 and r.json()["cancel_reason"] == "Отменён гостем"
    again = guest.post(f"/api/orders/{card['id']}/cancel")
    assert again.status_code == 409
    card2 = guest.post("/api/orders", json=order_body()).json()
    staff.post(f"/api/staff/orders/{card2['id']}/advance", json={"expected_status": "accepted"})
    late = guest.post(f"/api/orders/{card2['id']}/cancel")
    assert late.status_code == 409 and "сотрудник" in late.json()["error"]["message"]


def test_cart_check_for_favorites(guest, staff):
    staff.post("/api/staff/addons/oat/availability", json={"available": False})
    res = guest.post("/api/cart/check", json={"items": [LATTE]}).json()
    assert res["ok"] is False and "недоступна" in res["lines"][0]["problem"]


def test_order_survives_app_restart(tmp_path, clock):
    from fastapi.testclient import TestClient
    from app.config import Settings
    from app.main import create_app
    settings = Settings(db_path=str(tmp_path / "restart.db"))
    c1 = TestClient(create_app(settings=settings, clock=clock))
    card = c1.post("/api/orders", json=order_body()).json()
    token = c1.cookies.get("guest_token")
    c2 = TestClient(create_app(settings=settings, clock=clock), cookies={"guest_token": token})
    assert c2.get(f"/api/orders/{card['id']}").json()["number"] == card["number"]
