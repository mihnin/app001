"""HTTP-маршруты панели сотрудника. Все, кроме входа/выхода, требуют защищённой сессии."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request, Response

from app.api.deps import STAFF_COOKIE, get_ctx, parse_day, require_staff
from app.domain.errors import ForbiddenError
from app.services import auth_service, menu_service, slot_service, staff_service, summary_service
from app.services.context import Context

public = APIRouter(prefix="/api/staff", tags=["staff"])
router = APIRouter(prefix="/api/staff", tags=["staff"], dependencies=[Depends(require_staff)])


@public.post("/login")
def login(request: Request, response: Response, payload: dict = Body(...), ctx: Context = Depends(get_ctx)):
    token = auth_service.staff_login(ctx, payload.get("password"), request.app.state.settings.staff_password)
    if token is None:
        raise ForbiddenError("Неверный пароль сотрудника", code="bad_password")
    response.set_cookie(STAFF_COOKIE, token, httponly=True, samesite="strict")
    return {"staff": True}


@public.post("/logout")
def logout(request: Request, response: Response, ctx: Context = Depends(get_ctx)):
    auth_service.staff_logout(ctx, request.cookies.get(STAFF_COOKIE))
    response.delete_cookie(STAFF_COOKIE)
    return {"staff": False}


@public.get("/me")
def me(request: Request, ctx: Context = Depends(get_ctx)):
    return {"staff": auth_service.is_staff(ctx, request.cookies.get(STAFF_COOKIE))}


@router.get("/queue")
def queue(day: str | None = None, ctx: Context = Depends(get_ctx)):
    return staff_service.queue(ctx, parse_day(day))


@router.post("/orders/{order_id}/advance")
def advance(order_id: str, payload: dict = Body(...), ctx: Context = Depends(get_ctx)):
    return staff_service.advance(ctx, order_id, payload.get("expected_status"))


@router.post("/orders/{order_id}/cancel")
def cancel(order_id: str, payload: dict = Body(...), ctx: Context = Depends(get_ctx)):
    return staff_service.staff_cancel(ctx, order_id, payload.get("expected_status"), payload.get("reason"))


@router.post("/close-day")
def close_day(ctx: Context = Depends(get_ctx)):
    return staff_service.close_day(ctx)


@router.get("/menu")
def menu(ctx: Context = Depends(get_ctx)):
    return menu_service.get_menu(ctx)


@router.post("/drinks/{drink_id}/availability")
def drink_availability(drink_id: str, payload: dict = Body(...), ctx: Context = Depends(get_ctx)):
    menu_service.set_drink_available(ctx, drink_id, payload.get("available"))
    return menu_service.get_menu(ctx)


@router.post("/addons/{addon_id}/availability")
def addon_availability(addon_id: str, payload: dict = Body(...), ctx: Context = Depends(get_ctx)):
    menu_service.set_addon_available(ctx, addon_id, payload.get("available"))
    return menu_service.get_menu(ctx)


@router.post("/pause")
def pause(payload: dict = Body(...), ctx: Context = Depends(get_ctx)):
    menu_service.set_paused(ctx, payload.get("paused"))
    return menu_service.get_point(ctx)


@router.get("/slots")
def slots(ctx: Context = Depends(get_ctx)):
    return slot_service.list_slots(ctx)


@router.post("/slots/{key}/limit")
def set_limit(key: str, payload: dict = Body(...), ctx: Context = Depends(get_ctx)):
    return slot_service.set_limit(ctx, key, payload.get("limit"))


@router.get("/summary")
def summary(day: str | None = None, ctx: Context = Depends(get_ctx)):
    return summary_service.daily_summary(ctx, parse_day(day))
