"""ФТ-01, ФТ-14 / ПИ-01, ПИ-12."""
from app.db.database import Database
from app.db.seed import reset_demo
from app.services import auth_service, menu_service, order_service
from tests.conftest import GUEST_A, LATTE_M_OAT, LATTE_M_OAT_PRICE, new_attempt


def test_guest_token_hash_is_stable_and_not_raw():
    token = auth_service.new_token()
    assert len(token) >= 32
    assert auth_service.token_hash(token) == auth_service.token_hash(token)
    assert auth_service.token_hash(token) != token


def test_staff_login_logout(ctx):
    assert auth_service.staff_login(ctx, "wrong", "barista") is None
    token = auth_service.staff_login(ctx, "barista", "barista")
    assert token and auth_service.is_staff(ctx, token)
    assert not auth_service.is_staff(ctx, "forged")
    assert not auth_service.is_staff(ctx, None)
    auth_service.staff_logout(ctx, token)
    assert not auth_service.is_staff(ctx, token)


def test_data_survives_restart_until_reset(ctx):
    order_service.place_order(ctx, GUEST_A, new_attempt(), [LATTE_M_OAT], "", "10:30", LATTE_M_OAT_PRICE)
    menu_service.set_paused(ctx, True)
    reopened = Database(ctx.db.path)                  # «перезапуск»
    ctx2 = type(ctx)(db=reopened, clock=ctx.clock, profile=ctx.profile)
    assert len(order_service.list_guest_orders(ctx2, GUEST_A)) == 1
    assert menu_service.get_point(ctx2)["paused"] is True
    reset_demo(reopened)
    assert order_service.list_guest_orders(ctx2, GUEST_A) == []
    assert menu_service.get_point(ctx2)["paused"] is False
    assert len(menu_service.get_menu(ctx2)["drinks"]) >= 6
