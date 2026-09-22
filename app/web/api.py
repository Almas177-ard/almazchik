"""WebApp (do'kon) uchun API endpointlar."""
import json
import logging
import secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app import db
from app.partner import client as partner
from app.users import public_user, upsert_user
from app.web import catalog
from app.web.auth import (
    ApiError,
    clear_session_cookie,
    ensure_running,
    get_current_user,
    set_session_cookie,
    verify_init_data,
)

log = logging.getLogger("hamyon.api")
router = APIRouter(prefix="/api")

VALID_LANGS = ("uz", "ru", "en")
VALID_THEMES = ("light", "dark", "auto")


async def _public_config() -> dict:
    s = await db.get_all_settings()
    try:
        qty_max = int(s.get("order_quantity_max") or 50)
    except ValueError:
        qty_max = 50
    return {
        "appName": s.get("app_name") or "Hamyon",
        "supportUrl": s.get("support_url") or "",
        "deposit": {
            "network": s.get("deposit_network") or "",
            "address": s.get("deposit_address") or "",
            "note": s.get("deposit_note") or "",
        },
        "maintenance": s.get("maintenance") == "1",
        "defaultLang": s.get("default_lang") or "uz",
        "apiConfigured": bool((s.get("partner_api_key") or "").strip()),
        "startPhoto": "/" + (s.get("start_photo") or "img/hero.png").lstrip("/"),
        "quantityMax": qty_max,
    }


# ------------------------------------------------------------------ auth
@router.post("/auth")
async def auth(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    init_data = (body or {}).get("initData") or ""
    if not init_data:
        raise ApiError(401, "NO_INIT_DATA", "Bu ilovani Telegram ichida oching.")
    tg_user = verify_init_data(init_data)
    user = await upsert_user(
        tg_user.get("id"),
        username=tg_user.get("username"),
        first_name=tg_user.get("first_name"),
        last_name=tg_user.get("last_name"),
    )
    if user.get("blocked"):
        raise ApiError(403, "USER_BLOCKED", "Hisobingiz bloklangan.")
    resp = JSONResponse({"ok": True, "user": public_user(user), "public": await _public_config()})
    set_session_cookie(resp, int(tg_user["id"]), user.get("role") or "user", via="tg")
    return resp


@router.post("/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    clear_session_cookie(resp)
    return resp


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"ok": True, "user": public_user(user)}


@router.get("/public")
async def public():
    return {"ok": True, "public": await _public_config()}


@router.post("/prefs")
async def prefs(request: Request, user: dict = Depends(get_current_user)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    lang = (body or {}).get("lang")
    theme = (body or {}).get("theme")
    if lang and lang in VALID_LANGS:
        await db.execute("UPDATE users SET lang=%s WHERE tg_id=%s", (lang, user["tg_id"]))
    if theme and theme in VALID_THEMES:
        await db.execute("UPDATE users SET theme=%s WHERE tg_id=%s", (theme, user["tg_id"]))
    row = await db.fetch_one("SELECT * FROM users WHERE tg_id=%s", (user["tg_id"],))
    return {"ok": True, "user": public_user(row or user)}


# ------------------------------------------------------------------ balans / statistika
@router.get("/balance")
async def balance(user: dict = Depends(get_current_user)):
    await ensure_running()
    data = await partner.balance()
    return {
        "ok": True,
        "balance": data.get("balance", "0.00"),
        "currency": data.get("currency", "USD"),
    }


@router.get("/usage")
async def usage(user: dict = Depends(get_current_user)):
    await ensure_running()
    data = await partner.usage()
    if isinstance(data, dict):
        data.setdefault("ok", True)
    return data


# ------------------------------------------------------------------ katalog
@router.get("/providers")
async def providers(user: dict = Depends(get_current_user)):
    await ensure_running()
    return {"ok": True, "data": await catalog.get_providers()}


@router.get("/products")
async def products(provider: str = None, user: dict = Depends(get_current_user)):
    await ensure_running()
    return {"ok": True, "data": await catalog.get_products(provider)}


@router.get("/products/{ref}")
async def product_detail(ref: str, user: dict = Depends(get_current_user)):
    await ensure_running()
    item = await catalog.get_product(ref)
    return {"ok": True, "product": item}


# ------------------------------------------------------------------ buyurtmalar
def _qty_max_default():
    return 50


@router.post("/orders")
async def create_order(request: Request, user: dict = Depends(get_current_user)):
    await ensure_running()
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "VALIDATION_ERROR", "So'rov formati noto'g'ri.")
    body = body or {}

    refs = {
        "productSlug": body.get("productSlug"),
        "productId": body.get("productId"),
        "productCode": body.get("productCode"),
    }
    chosen = {k: v for k, v in refs.items() if v not in (None, "")}
    if len(chosen) != 1:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "Mahsulot uchun productSlug, productId yoki productCode dan bittasi kerak.",
        )

    try:
        qty_max = int(await db.get_setting("order_quantity_max", "50") or 50)
    except ValueError:
        qty_max = _qty_max_default()
    try:
        quantity = int(body.get("quantity", 1))
    except (TypeError, ValueError):
        raise ApiError(400, "INVALID_QUANTITY", "Miqdor noto'g'ri kiritildi.")
    if quantity < 1 or quantity > qty_max:
        raise ApiError(
            400,
            "INVALID_QUANTITY",
            f"Miqdor 1 dan {qty_max} gacha bo'lishi kerak.",
        )

    payload = {**chosen, "quantity": quantity}
    payload["externalOrderId"] = (
        f"HY-{user['tg_id']}-{int(time.time() * 1000)}-{secrets.token_hex(3).upper()}"
    )

    resp = await partner.create_order(payload)
    if not isinstance(resp, dict) or resp.get("ok") is False:
        raise ApiError(502, "FAILED", "Buyurtma yaratilmadi.")

    product_info = resp.get("product") or {}
    created_at = resp.get("createdAt")
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
    delivery_json = json.dumps(
        {"delivery": resp.get("delivery"), "lines": resp.get("lines")}, ensure_ascii=False
    )
    await db.execute(
        """INSERT INTO orders (tg_id, order_code, external_order_id, product_slug, product_name,
                               delivery_type, quantity, unit_price, total_charged, status,
                               delivery_json, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE delivery_json=VALUES(delivery_json), status=VALUES(status)""",
        (
            user["tg_id"],
            resp.get("orderCode") or payload["externalOrderId"],
            payload["externalOrderId"],
            product_info.get("slug") or chosen.get("productSlug"),
            product_info.get("name"),
            resp.get("deliveryType"),
            resp.get("quantity", quantity),
            resp.get("unitPrice"),
            resp.get("totalCharged"),
            resp.get("status"),
            delivery_json,
            created_at[:19].replace("T", " ") if "T" in str(created_at) else created_at,
        ),
    )
    return JSONResponse({"ok": True, **{k: v for k, v in resp.items() if k != "ok"}})


def _order_row_public(row: dict, include_delivery: bool = False) -> dict:
    out = {
        "orderCode": row.get("order_code"),
        "externalOrderId": row.get("external_order_id"),
        "status": row.get("status"),
        "deliveryType": row.get("delivery_type"),
        "product": {"slug": row.get("product_slug"), "name": row.get("product_name")},
        "quantity": row.get("quantity"),
        "unitPrice": str(row.get("unit_price")) if row.get("unit_price") is not None else None,
        "totalCharged": (
            str(row.get("total_charged")) if row.get("total_charged") is not None else None
        ),
        "currency": "USD",
        "createdAt": str(row.get("created_at") or ""),
    }
    if include_delivery and row.get("delivery_json"):
        try:
            dj = json.loads(row["delivery_json"])
            if dj.get("delivery"):
                out["delivery"] = dj["delivery"]
            if dj.get("lines"):
                out["lines"] = dj["lines"]
        except Exception:
            pass
    return out


@router.get("/orders")
async def list_orders(
    page: int = 1, limit: int = 20, user: dict = Depends(get_current_user)
):
    page = max(1, page)
    limit = min(max(1, limit), 100)
    total_row = await db.fetch_one(
        "SELECT COUNT(*) AS c FROM orders WHERE tg_id=%s", (user["tg_id"],)
    )
    total = int(total_row["c"]) if total_row else 0
    rows = await db.fetch(
        "SELECT * FROM orders WHERE tg_id=%s ORDER BY id DESC LIMIT %s OFFSET %s",
        (user["tg_id"], limit, (page - 1) * limit),
    )
    return {
        "ok": True,
        "data": [_order_row_public(r) for r in rows],
        "meta": {"page": page, "limit": limit, "total": total,
                 "totalPages": (total + limit - 1) // limit if total else 0},
    }


@router.get("/orders/{order_code}")
async def order_detail(order_code: str, user: dict = Depends(get_current_user)):
    row = await db.fetch_one(
        "SELECT * FROM orders WHERE order_code=%s AND tg_id=%s", (order_code, user["tg_id"])
    )
    if row:
        return {"ok": True, **_order_row_public(row, include_delivery=True)}
    # lokal keshda bo'lmasa — to'g'ridan-to'g'ri API dan (faqat o'z buyurtmasi)
    data = await partner.order_detail(order_code)
    return JSONResponse({"ok": True, **{k: v for k, v in (data or {}).items() if k != "ok"}})
