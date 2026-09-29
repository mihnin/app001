"""HTTP-маршруты гостя."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Response

from app.api.deps import get_ctx, guest_id
from app.services import menu_service, order_service, slot_service
from app.services.context import Context

router = APIRouter(prefix="/api", tags=["guest"])


@router.get("/point")
def point(ctx: Context = Depends(get_ctx)):
    return menu_service.get_point(ctx)


@router.get("/menu")
def menu(ctx: Context = Depends(get_ctx)):
    return menu_service.get_menu(ctx)


@router.get("/slots")
def slots(qty: int = Query(1, ge=1, le=100), ctx: Context = Depends(get_ctx)):
    return slot_service.list_slots(ctx, qty)


@router.post("/cart/check")
def cart_check(payload: dict = Body(...), ctx: Context = Depends(get_ctx)):
    return menu_service.check_cart(ctx, payload.get("items"))


@router.post("/orders")
def place_order(response: Response, payload: dict = Body(...), ctx: Context = Depends(get_ctx),
                guest: str = Depends(guest_id)):
    card, replayed = order_service.place_order(
        ctx, guest, payload.get("attempt_id"), payload.get("items"), payload.get("wish"),
        payload.get("slot"), payload.get("expected_total"),
    )
    response.status_code = 200 if replayed else 201   # тот же Response, что несёт гостевую cookie
    return {**card, "replayed": replayed}


@router.get("/orders")
def my_orders(ctx: Context = Depends(get_ctx), guest: str = Depends(guest_id)):
    return order_service.list_guest_orders(ctx, guest)


@router.get("/orders/{order_id}")
def my_order(order_id: str, ctx: Context = Depends(get_ctx), guest: str = Depends(guest_id)):
    return order_service.get_guest_order(ctx, guest, order_id)


@router.post("/orders/{order_id}/cancel")
def cancel(order_id: str, ctx: Context = Depends(get_ctx), guest: str = Depends(guest_id)):
    return order_service.guest_cancel(ctx, guest, order_id)


@router.get("/attempts/{attempt_id}")
def attempt(attempt_id: str, ctx: Context = Depends(get_ctx), guest: str = Depends(guest_id)):
    return order_service.get_attempt(ctx, guest, attempt_id)
