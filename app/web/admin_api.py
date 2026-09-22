"""Admin panel API — barcha sozlamalar, foydalanuvchilar, buyurtmalar,
katalog, matnlar va rasmlarni boshqarish."""
import json
import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import JSONResponse

from app import db
from app.i18n import DEFAULT_TEXTS, SUPPORTED_LANGS, default_text, text_keys
from app.partner import client as partner
from app.web import catalog
from app.web.auth import (
    ApiError,
    clear_session_cookie,
    require_admin,
    set_session_cookie,
)
from app.config import STATIC_DIR

log = logging.getLogger("hamyon.admin")
router = APIRouter(prefix="/admin/api")

SETTINGS_KEYS = {
    "partner_base_url", "partner_api_key", "app_name", "webapp_url", "support_url",
    "deposit_network", "deposit_address", "deposit_note", "default_lang",
    "cache_ttl", "order_quantity_max", "maintenance", "start_photo",
}

MASK = "••••"


# ------------------------------------------------------------------ login
@router.post("/login")
async def login(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    password = (body or {}).get("password") or ""
    stored = await db.get_setting("admin_password_hash")
    from app.db import hash_password

    if not stored or hash_password(password) != stored:
        raise ApiError(401, "WRONG_PASSWORD", "Parol noto'g'ri.")
    resp = JSONResponse({"ok": True})
    set_session_cookie(resp, 0, "admin", via="password")
    return resp


@router.post("/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    clear_session_cookie(resp)
    return resp


@router.get("/me")
async def me(admin: dict = Depends(require_admin)):
    return {"ok": True, "role": "admin", "tgId": admin.get("tg_id") or 0}


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard")
async def dashboard(admin: dict = Depends(require_admin)):
    users_total = (await db.fetch_one("SELECT COUNT(*) AS c FROM users"))["c"]
    users_24h = (
        await db.fetch_one(
            "SELECT COUNT(*) AS c FROM users WHERE created_at >= NOW() - INTERVAL 1 DAY"
        )
    )["c"]
    orders_total = (await db.fetch_one("SELECT COUNT(*) AS c FROM orders"))["c"]
    orders_24h = (
        await db.fetch_one(
            "SELECT COUNT(*) AS c FROM orders WHERE created_at >= NOW() - INTERVAL 1 DAY"
        )
    )["c"]
    spend_row = await db.fetch_one(
        "SELECT COALESCE(SUM(total_charged), 0) AS s FROM orders "
        "WHERE created_at >= NOW() - INTERVAL 1 DAY"
    )
    maintenance = (await db.get_setting("maintenance")) == "1"

    balance = None
    api_online = False
    try:
        h = await partner.health()
        api_online = bool(h.get("ok"))
        b = await partner.balance()
        balance = {"balance": b.get("balance"), "currency": b.get("currency", "USD")}
    except Exception:
        pass

    return {
        "ok": True,
        "stats": {
            "usersTotal": int(users_total or 0),
            "users24h": int(users_24h or 0),
            "ordersTotal": int(orders_total or 0),
            "orders24h": int(orders_24h or 0),
            "spend24h": str(spend_row["s"] or "0.00"),
        },
        "balance": balance,
        "apiOnline": api_online,
        "maintenance": maintenance,
    }


# ------------------------------------------------------------------ sozlamalar
@router.get("/settings")
async def get_settings(reveal: int = 0, admin: dict = Depends(require_admin)):
    s = await db.get_all_settings(force=True)
    out = {k: s.get(k, "") for k in SETTINGS_KEYS}
    key = out.get("partner_api_key") or ""
    if key and not reveal:
        out["partner_api_key"] = MASK + (key[-4:] if len(key) > 4 else "")
    return {"ok": True, "settings": out}


@router.post("/settings")
async def save_settings(request: Request, admin: dict = Depends(require_admin)):
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "VALIDATION_ERROR", "JSON formati noto'g'ri.")
    body = body or {}
    saved = []
    for key, value in body.items():
        if key not in SETTINGS_KEYS:
            continue
        if key == "partner_api_key" and isinstance(value, str) and value.startswith(MASK):
            continue  # niqoblangan qiymat o'zgartirilmaydi
        if key == "maintenance":
            value = "1" if value in (1, "1", True, "true") else "0"
        if key in ("cache_ttl", "order_quantity_max"):
            try:
                value = str(max(1, int(value)))
            except (TypeError, ValueError):
                raise ApiError(400, "VALIDATION_ERROR", f"{key} son bo'lishi kerak.")
        if key == "default_lang" and value not in SUPPORTED_LANGS:
            raise ApiError(400, "VALIDATION_ERROR", "Til uz/ru/en dan biri bo'lishi kerak.")
        if key == "partner_base_url":
            value = str(value or "").strip().rstrip("/")
            if value and not value.startswith(("http://", "https://")):
                raise ApiError(400, "VALIDATION_ERROR", "Base URL http(s):// bilan boshlanishi kerak.")
        await db.set_setting(key, str(value or "").strip())
        saved.append(key)
    return {"ok": True, "saved": saved}


@router.post("/password")
async def change_password(request: Request, admin: dict = Depends(require_admin)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    current = (body or {}).get("current") or ""
    new = (body or {}).get("next") or ""
    from app.db import hash_password

    stored = await db.get_setting("admin_password_hash")
    if not stored or hash_password(current) != stored:
        raise ApiError(401, "WRONG_PASSWORD", "Joriy parol noto'g'ri.")
    if len(new) < 6:
        raise ApiError(400, "VALIDATION_ERROR", "Yangi parol kamida 6 belgidan iborat bo'lsin.")
    await db.set_setting("admin_password_hash", hash_password(new))
    return {"ok": True}


# ------------------------------------------------------------------ foydalanuvchilar
@router.get("/users")
async def list_users(
    q: str = "", limit: int = 20, offset: int = 0, admin: dict = Depends(require_admin)
):
    limit = min(max(1, limit), 100)
    offset = max(0, offset)
    where, args = "", []
    if q.strip():
        like = f"%{q.strip()}%"
        if q.strip().isdigit():
            where = "WHERE tg_id=%s OR username LIKE %s OR first_name LIKE %s"
            args = [int(q.strip()), like, like]
        else:
            where = "WHERE username LIKE %s OR first_name LIKE %s OR last_name LIKE %s"
            args = [like, like, like]
    total = (
        await db.fetch_one(f"SELECT COUNT(*) AS c FROM users {where}", args)
    )["c"]
    rows = await db.fetch(
        f"SELECT * FROM users {where} ORDER BY last_seen DESC LIMIT %s OFFSET %s",
        [*args, limit, offset],
    )
    for r in rows:
        r["created_at"] = str(r.get("created_at") or "")
        r["last_seen"] = str(r.get("last_seen") or "")
    return {"ok": True, "data": rows, "meta": {"total": int(total or 0), "limit": limit, "offset": offset}}


@router.post("/users/{tg_id}")
async def update_user(tg_id: int, request: Request, admin: dict = Depends(require_admin)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}
    sets, args = [], []
    if "blocked" in body:
        sets.append("blocked=%s")
        args.append(1 if body["blocked"] else 0)
    if body.get("role") in ("user", "admin"):
        sets.append("role=%s")
        args.append(body["role"])
    if body.get("lang") in SUPPORTED_LANGS:
        sets.append("lang=%s")
        args.append(body["lang"])
    if not sets:
        raise ApiError(400, "VALIDATION_ERROR", "O'zgartiriladigan maydon topilmadi.")
    args.append(tg_id)
    await db.execute(f"UPDATE users SET {', '.join(sets)} WHERE tg_id=%s", args)
    row = await db.fetch_one("SELECT * FROM users WHERE tg_id=%s", (tg_id,))
    if not row:
        raise ApiError(404, "NOT_FOUND", "Foydalanuvchi topilmadi.")
    row["created_at"] = str(row.get("created_at") or "")
    row["last_seen"] = str(row.get("last_seen") or "")
    return {"ok": True, "user": row}


# ------------------------------------------------------------------ buyurtmalar
@router.get("/orders")
async def list_orders(
    q: str = "", limit: int = 20, offset: int = 0, admin: dict = Depends(require_admin)
):
    limit = min(max(1, limit), 100)
    offset = max(0, offset)
    where, args = "", []
    if q.strip():
        like = f"%{q.strip()}%"
        where = "WHERE order_code LIKE %s OR external_order_id LIKE %s OR product_name LIKE %s"
        args = [like, like, like]
    total = (await db.fetch_one(f"SELECT COUNT(*) AS c FROM orders {where}", args))["c"]
    rows = await db.fetch(
        f"SELECT id, tg_id, order_code, external_order_id, product_slug, product_name, "
        f"delivery_type, quantity, unit_price, total_charged, status, created_at "
        f"FROM orders {where} ORDER BY id DESC LIMIT %s OFFSET %s",
        [*args, limit, offset],
    )
    for r in rows:
        r["created_at"] = str(r.get("created_at") or "")
        r["unit_price"] = str(r["unit_price"]) if r.get("unit_price") is not None else None
        r["total_charged"] = str(r["total_charged"]) if r.get("total_charged") is not None else None
    return {"ok": True, "data": rows, "meta": {"total": int(total or 0), "limit": limit, "offset": offset}}


@router.get("/orders/{code}")
async def order_detail(code: str, admin: dict = Depends(require_admin)):
    row = await db.fetch_one("SELECT * FROM orders WHERE order_code=%s", (code,))
    if not row:
        raise ApiError(404, "ORDER_NOT_FOUND", "Buyurtma topilmadi.")
    row["created_at"] = str(row.get("created_at") or "")
    row["unit_price"] = str(row["unit_price"]) if row.get("unit_price") is not None else None
    row["total_charged"] = str(row["total_charged"]) if row.get("total_charged") is not None else None
    delivery = None
    if row.get("delivery_json"):
        try:
            delivery = json.loads(row["delivery_json"])
        except Exception:
            delivery = None
    row["delivery_json"] = delivery
    return {"ok": True, "order": row}


# ------------------------------------------------------------------ katalog
@router.post("/catalog/sync")
async def sync_catalog(admin: dict = Depends(require_admin)):
    try:
        counts = await catalog.sync_all(force=True)
    except Exception as exc:
        raise ApiError(502, "SYNC_FAILED", f"Katalog yangilanmadi: {exc}")
    return {"ok": True, **counts}


@router.get("/catalog/products")
async def catalog_products(q: str = "", admin: dict = Depends(require_admin)):
    rows = await db.fetch("SELECT slug, payload FROM products_cache ORDER BY product_id")
    blocked_rows = await db.fetch("SELECT product_slug FROM product_blocks")
    blocked = {r["product_slug"] for r in blocked_rows}
    out = []
    q = q.strip().lower()
    for r in rows:
        try:
            item = json.loads(r["payload"])
        except Exception:
            continue
        if q and q not in (item.get("name") or "").lower() and q not in (item.get("slug") or "").lower():
            continue
        provider = item.get("provider") or {}
        stock = item.get("stock") or {}
        out.append(
            {
                "slug": item.get("slug"),
                "name": item.get("name"),
                "provider": provider.get("name") or provider.get("key"),
                "deliveryType": item.get("deliveryType"),
                "yourPrice": item.get("yourPrice"),
                "stockCount": stock.get("count"),
                "inStock": stock.get("inStock"),
                "blocked": (item.get("slug") in blocked),
            }
        )
    return {"ok": True, "data": out}


@router.post("/catalog/products/{slug}/toggle")
async def toggle_product(slug: str, request: Request, admin: dict = Depends(require_admin)):
    row = await db.fetch_one("SELECT product_slug FROM product_blocks WHERE product_slug=%s", (slug,))
    if row:
        await db.execute("DELETE FROM product_blocks WHERE product_slug=%s", (slug,))
        blocked = False
    else:
        reason = ""
        try:
            body = await request.json()
            reason = (body or {}).get("reason") or ""
        except Exception:
            pass
        await db.execute(
            "INSERT IGNORE INTO product_blocks (product_slug, reason) VALUES (%s, %s)",
            (slug, reason[:255]),
        )
        blocked = True
    return {"ok": True, "slug": slug, "blocked": blocked}


# ------------------------------------------------------------------ matnlar
@router.get("/texts")
async def get_texts(lang: str = "uz", admin: dict = Depends(require_admin)):
    if lang not in SUPPORTED_LANGS:
        lang = "uz"
    rows = await db.fetch("SELECT tkey, value FROM texts WHERE lang=%s", (lang,))
    overrides = {r["tkey"]: r["value"] for r in rows}
    out = []
    for key in text_keys():
        val = overrides.get(key)
        out.append(
            {
                "key": key,
                "value": val if val is not None else default_text(key, lang),
                "overridden": val is not None,
                "default": default_text(key, lang),
            }
        )
    return {"ok": True, "lang": lang, "langs": list(SUPPORTED_LANGS), "data": out}


@router.post("/texts")
async def save_text(request: Request, admin: dict = Depends(require_admin)):
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "VALIDATION_ERROR", "JSON formati noto'g'ri.")
    key = (body or {}).get("key") or ""
    lang = (body or {}).get("lang") or "uz"
    value = (body or {}).get("value")
    if key not in DEFAULT_TEXTS:
        raise ApiError(400, "VALIDATION_ERROR", "Bunday matn kaliti yo'q.")
    if lang not in SUPPORTED_LANGS:
        raise ApiError(400, "VALIDATION_ERROR", "Til noto'g'ri.")
    if value is None or value == "" or value == default_text(key, lang):
        await db.execute("DELETE FROM texts WHERE tkey=%s AND lang=%s", (key, lang))
        return {"ok": True, "overridden": False}
    await db.execute(
        "INSERT INTO texts (tkey, lang, value) VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE value=VALUES(value)",
        (key, lang, value),
    )
    return {"ok": True, "overridden": True}


# ------------------------------------------------------------------ rasmlar
UPLOAD_DIR = STATIC_DIR / "img" / "uploads"
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_UPLOAD = 6 * 1024 * 1024


@router.get("/images")
async def list_images(admin: dict = Depends(require_admin)):
    rows = await db.fetch("SELECT * FROM images ORDER BY id DESC")
    start_photo = await db.get_setting("start_photo", "img/hero.png")
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "name": r.get("name"),
                "url": "/" + r["path"].lstrip("/"),
                "path": r["path"],
                "createdAt": str(r.get("created_at") or ""),
                "isStartPhoto": r["path"] == start_photo,
            }
        )
    return {"ok": True, "data": out, "startPhoto": start_photo}


@router.post("/images")
async def upload_image(file: UploadFile = File(...), admin: dict = Depends(require_admin)):
    name = file.filename or "image"
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        raise ApiError(400, "BAD_FILE", "Faqat jpg/png/webp/gif rasmlar qabul qilinadi.")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise ApiError(400, "FILE_TOO_LARGE", "Rasm 6 MB dan katta bo'lmasin.")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = f"img/uploads/{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}{ext}"
    (STATIC_DIR / path).write_bytes(data)
    img_id = await db.execute(
        "INSERT INTO images (name, path) VALUES (%s, %s)", (name[:128], path)
    )
    return {"ok": True, "id": img_id, "url": "/" + path, "path": path}


@router.post("/images/{img_id}/use")
async def use_image(img_id: int, admin: dict = Depends(require_admin)):
    row = await db.fetch_one("SELECT path FROM images WHERE id=%s", (img_id,))
    if not row:
        raise ApiError(404, "NOT_FOUND", "Rasm topilmadi.")
    await db.set_setting("start_photo", row["path"])
    return {"ok": True, "startPhoto": row["path"]}


@router.delete("/images/{img_id}")
async def delete_image(img_id: int, admin: dict = Depends(require_admin)):
    row = await db.fetch_one("SELECT path FROM images WHERE id=%s", (img_id,))
    if not row:
        raise ApiError(404, "NOT_FOUND", "Rasm topilmadi.")
    start_photo = await db.get_setting("start_photo", "img/hero.png")
    if row["path"] == start_photo:
        await db.set_setting("start_photo", "img/hero.png")
    try:
        (STATIC_DIR / row["path"]).unlink(missing_ok=True)
    except Exception:
        pass
    await db.execute("DELETE FROM images WHERE id=%s", (img_id,))
    return {"ok": True}
