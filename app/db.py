"""MySQL ulanish pooli, jadval sxemasi va sozlamalar keshi."""
import hashlib
import logging
import time

import aiomysql

from app.config import CFG

log = logging.getLogger("hamyon.db")

POOL = None
_settings = {"data": {}, "ts": 0.0}

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS settings (
        skey VARCHAR(64) NOT NULL PRIMARY KEY,
        sval TEXT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS users (
        tg_id BIGINT NOT NULL PRIMARY KEY,
        username VARCHAR(64) NULL,
        first_name VARCHAR(128) NULL,
        last_name VARCHAR(128) NULL,
        lang VARCHAR(8) NOT NULL DEFAULT 'uz',
        theme VARCHAR(8) NOT NULL DEFAULT 'auto',
        role VARCHAR(16) NOT NULL DEFAULT 'user',
        blocked TINYINT(1) NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS orders (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        tg_id BIGINT NOT NULL,
        order_code VARCHAR(64) NOT NULL,
        external_order_id VARCHAR(128) NOT NULL,
        product_slug VARCHAR(128) NULL,
        product_name VARCHAR(255) NULL,
        delivery_type VARCHAR(32) NULL,
        quantity INT NOT NULL DEFAULT 1,
        unit_price DECIMAL(12,2) NULL,
        total_charged DECIMAL(12,2) NULL,
        status VARCHAR(32) NULL,
        delivery_json MEDIUMTEXT NULL,
        created_at DATETIME NOT NULL,
        UNIQUE KEY uq_order_code (order_code),
        KEY idx_orders_tg (tg_id),
        KEY idx_orders_ext (external_order_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS texts (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        tkey VARCHAR(128) NOT NULL,
        lang VARCHAR(8) NOT NULL,
        value TEXT NOT NULL,
        UNIQUE KEY uq_texts (tkey, lang)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS product_blocks (
        product_slug VARCHAR(128) NOT NULL PRIMARY KEY,
        reason VARCHAR(255) NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS providers_cache (
        provider_id INT NOT NULL PRIMARY KEY,
        payload MEDIUMTEXT NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS products_cache (
        product_id INT NOT NULL PRIMARY KEY,
        slug VARCHAR(128) NOT NULL,
        payload MEDIUMTEXT NOT NULL,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_products_slug (slug)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS cache_meta (
        mkey VARCHAR(64) NOT NULL PRIMARY KEY,
        mval TEXT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS images (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(128) NULL,
        path VARCHAR(255) NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
)

DEFAULT_SETTINGS = {
    "partner_base_url": "https://hamyon-api.uz/api/partner/v1",
    "partner_api_key": "",
    "app_name": "Hamyon",
    "webapp_url": "",
    "support_url": "",
    "deposit_network": "",
    "deposit_address": "",
    "deposit_note": "",
    "default_lang": "uz",
    "cache_ttl": "90",
    "order_quantity_max": "50",
    "maintenance": "0",
    "start_photo": "img/hero.png",
    "admin_password_hash": "",
}

SALT = "hamyon::"


def hash_password(password: str) -> str:
    return hashlib.sha256((SALT + password).encode("utf-8")).hexdigest()


def default_admin_hash() -> str:
    return hash_password("admin123")


async def init_db():
    """Ma'lumotlar bazasini yaratadi, jadvallarni quradi va standart sozlamalarni yozadi."""
    global POOL
    base = dict(host=CFG.db_host, port=CFG.db_port, user=CFG.db_user, password=CFG.db_password)
    conn = await aiomysql.connect(**base, autocommit=True)
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "CREATE DATABASE IF NOT EXISTS `{}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci".format(CFG.db_name)
            )
    finally:
        conn.close()

    POOL = await aiomysql.create_pool(
        **base,
        db=CFG.db_name,
        charset="utf8mb4",
        autocommit=True,
        minsize=1,
        maxsize=10,
    )
    async with POOL.acquire() as conn:
        async with conn.cursor() as cur:
            for stmt in SCHEMA:
                await cur.execute(stmt)
            for key, val in DEFAULT_SETTINGS.items():
                await cur.execute(
                    "INSERT IGNORE INTO settings (skey, sval) VALUES (%s, %s)", (key, val)
                )
            if CFG.webapp_url:
                await cur.execute(
                    "UPDATE settings SET sval=%s WHERE skey='webapp_url' "
                    "AND (sval IS NULL OR sval='')",
                    (CFG.webapp_url,),
                )
            await cur.execute(
                "UPDATE settings SET sval=%s WHERE skey='admin_password_hash' "
                "AND (sval IS NULL OR sval='')",
                (default_admin_hash(),),
            )
    await refresh_settings(force=True)
    log.info("MySQL tayyor: %s@%s:%s/%s", CFG.db_user, CFG.db_host, CFG.db_port, CFG.db_name)


async def close_db():
    global POOL
    if POOL is not None:
        POOL.close()
        await POOL.wait_closed()
        POOL = None


async def fetch(sql, args=None):
    async with POOL.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args)
            return await cur.fetchall()


async def fetch_one(sql, args=None):
    rows = await fetch(sql, args)
    return rows[0] if rows else None


async def execute(sql, args=None):
    async with POOL.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, args)
            return cur.lastrowid


# ---------------------------------------------------------------- sozlamalar
async def refresh_settings(force: bool = False):
    now = time.monotonic()
    if not force and _settings["data"] and now - _settings["ts"] < 20:
        return _settings["data"]
    rows = await fetch("SELECT skey, sval FROM settings")
    _settings["data"] = {r["skey"]: ("" if r["sval"] is None else str(r["sval"])) for r in rows}
    _settings["ts"] = now
    return _settings["data"]


async def get_setting(key: str, default: str = "") -> str:
    data = await refresh_settings()
    val = data.get(key)
    return val if val not in (None, "") else default


async def set_setting(key: str, value):
    value = "" if value is None else str(value)
    await execute(
        "INSERT INTO settings (skey, sval) VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE sval=VALUES(sval)",
        (key, value),
    )
    _settings["data"][key] = value


async def get_all_settings(force: bool = False):
    return dict(await refresh_settings(force=force))
