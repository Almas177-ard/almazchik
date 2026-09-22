"""Katalog keshi: Partner API dan olingan provider/product lar DB da saqlanadi.

TTL (cache_ttl sozlamasi) ichida so'rovlar keshdan beriladi; API yiqilsa
eskirgan kesh zaxira sifatida ko'rsatiladi.
"""
import json
import time

from app import db
from app.partner import client as partner
from app.web.auth import ApiError


async def _meta_get(key: str):
    row = await db.fetch_one("SELECT mval FROM cache_meta WHERE mkey=%s", (key,))
    return row["mval"] if row else None


async def _meta_set(key: str, value):
    await db.execute(
        "INSERT INTO cache_meta (mkey, mval) VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE mval=VALUES(mval)",
        (key, str(value)),
    )


async def _cache_ttl() -> int:
    try:
        return max(10, int(await db.get_setting("cache_ttl", "90") or 90))
    except ValueError:
        return 90


async def _is_fresh(key: str) -> bool:
    ts = await _meta_get(key)
    if not ts:
        return False
    try:
        return (time.time() - float(ts)) < await _cache_ttl()
    except ValueError:
        return False


async def _blocked_slugs() -> set:
    rows = await db.fetch("SELECT product_slug FROM product_blocks")
    return {r["product_slug"] for r in rows}


async def sync_providers(force: bool = False) -> int:
    if not force and await _is_fresh("providers_at"):
        rows = await db.fetch("SELECT COUNT(*) AS c FROM providers_cache")
        return rows[0]["c"]
    data = await partner.providers()
    for item in data:
        await db.execute(
            "INSERT INTO providers_cache (provider_id, payload) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE payload=VALUES(payload), updated_at=CURRENT_TIMESTAMP",
            (item.get("id"), json.dumps(item, ensure_ascii=False)),
        )
    await _meta_set("providers_at", time.time())
    return len(data)


async def sync_products(force: bool = False) -> int:
    if not force and await _is_fresh("products_at"):
        rows = await db.fetch("SELECT COUNT(*) AS c FROM products_cache")
        return rows[0]["c"]
    data = await partner.products()
    seen = []
    for item in data:
        pid = item.get("id")
        slug = item.get("slug") or ""
        seen.append(pid)
        await db.execute(
            "INSERT INTO products_cache (product_id, slug, payload) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE slug=VALUES(slug), payload=VALUES(payload), "
            "updated_at=CURRENT_TIMESTAMP",
            (pid, slug, json.dumps(item, ensure_ascii=False)),
        )
    if seen:
        fmt = ",".join(["%s"] * len(seen))
        await db.execute(f"DELETE FROM products_cache WHERE product_id NOT IN ({fmt})", seen)
    await _meta_set("products_at", time.time())
    return len(data)


async def sync_all(force: bool = False) -> dict:
    providers_count = await sync_providers(force=force)
    products_count = await sync_products(force=force)
    return {"providers": providers_count, "products": products_count}


async def get_providers() -> list:
    try:
        await sync_providers()
    except Exception:
        pass  # eskirgan keshdan foydalanamiz
    rows = await db.fetch("SELECT payload FROM providers_cache ORDER BY provider_id")
    out = []
    for r in rows:
        try:
            out.append(json.loads(r["payload"]))
        except Exception:
            continue
    out.sort(key=lambda x: (x.get("sortOrder") or 0, x.get("id") or 0))
    return out


async def get_products(provider: str = None) -> list:
    try:
        await sync_products()
    except Exception:
        pass
    rows = await db.fetch("SELECT payload FROM products_cache ORDER BY product_id")
    blocked = await _blocked_slugs()
    out = []
    for r in rows:
        try:
            item = json.loads(r["payload"])
        except Exception:
            continue
        if item.get("slug") in blocked:
            continue
        p = item.get("provider") or {}
        if provider and p.get("key") != provider:
            continue
        out.append(item)
    out.sort(key=lambda x: (x.get("sortOrder") or 0, x.get("id") or 0))
    return out


async def get_product(ref: str) -> dict:
    """Bitta mahsulot: avval keshdan, bo'lmasa to'g'ridan-to'g'ri API dan."""
    blocked = await _blocked_slugs()
    ref_s = str(ref).strip()
    row = None
    if ref_s.isdigit():
        row = await db.fetch_one(
            "SELECT payload FROM products_cache WHERE product_id=%s", (int(ref_s),)
        )
    else:
        row = await db.fetch_one("SELECT payload FROM products_cache WHERE slug=%s", (ref_s,))
    if row:
        try:
            item = json.loads(row["payload"])
            if item.get("slug") in blocked:
                raise ApiError(400, "PRODUCT_BLOCKED", "Bu mahsulot hozirda sotuvda emas.")
            return item
        except json.JSONDecodeError:
            pass
    live = await partner.product(ref_s)
    if isinstance(live, dict) and live.get("slug") in blocked:
        raise ApiError(400, "PRODUCT_BLOCKED", "Bu mahsulot hozirda sotuvda emas.")
    return live


async def catalog_updated_at():
    ts = await _meta_get("products_at")
    try:
        return float(ts) if ts else None
    except ValueError:
        return None
