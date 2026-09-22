"""Autentifikatsiya: Telegram WebApp initData tekshiruvi va session cookie."""
import base64
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Request, Response

from app import db
from app.config import CFG

SESSION_COOKIE = "hy_session"
SESSION_TTL = 30 * 86400
INIT_DATA_MAX_AGE = 86400


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, extra=None):
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra


# ------------------------------------------------------------ initData (Telegram)
def verify_init_data(init_data: str) -> dict:
    """Telegram WebApp initData imzosini bot token orqali tekshiradi."""
    try:
        params = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        raise ApiError(400, "BAD_INIT_DATA", "initData formati noto'g'ri.")
    check_hash = params.pop("hash", None)
    if not check_hash or "auth_date" not in params or "user" not in params:
        raise ApiError(401, "BAD_INIT_DATA", "initData to'liq emas.")
    try:
        auth_date = int(params["auth_date"])
    except ValueError:
        raise ApiError(401, "BAD_INIT_DATA", "auth_date noto'g'ri.")
    if time.time() - auth_date > INIT_DATA_MAX_AGE:
        raise ApiError(401, "INIT_DATA_EXPIRED", "Sessiya eskirgan. Ilovani qayta oching.")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", CFG.bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, check_hash.lower()):
        raise ApiError(401, "BAD_SIGNATURE", "initData imzosi mos kelmadi.")
    try:
        user = json.loads(params["user"])
    except Exception:
        raise ApiError(401, "BAD_INIT_DATA", "user payload noto'g'ri.")
    if not isinstance(user, dict) or "id" not in user:
        raise ApiError(401, "BAD_INIT_DATA", "user payload noto'liq.")
    return user


# ------------------------------------------------------------ session token
def _sign(body: str) -> str:
    return hmac.new(CFG.session_secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def create_session_token(payload: dict) -> str:
    payload = dict(payload)
    payload["exp"] = int(time.time()) + SESSION_TTL
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{body}.{_sign(body)}"


def read_session(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(body), sig):
        return None
    try:
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


def set_session_cookie(response: Response, uid: int, role: str, via: str = "tg"):
    token = create_session_token({"uid": uid, "role": role, "via": via})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")


# ------------------------------------------------------------ dependency'lar
async def get_current_user(request: Request) -> dict:
    payload = read_session(request)
    if not payload:
        raise ApiError(401, "UNAUTHORIZED", "Sessiya topilmadi. Ilovani qayta oching.")
    if payload.get("via") == "password" and payload.get("role") == "admin":
        return {
            "tg_id": 0,
            "role": "admin",
            "lang": "uz",
            "theme": "auto",
            "blocked": 0,
            "first_name": "Admin",
            "username": None,
        }
    row = await db.fetch_one("SELECT * FROM users WHERE tg_id=%s", (payload.get("uid"),))
    if not row:
        raise ApiError(401, "UNAUTHORIZED", "Foydalanuvchi topilmadi.")
    if row.get("blocked"):
        raise ApiError(403, "USER_BLOCKED", "Hisobingiz bloklangan.")
    return row


async def require_admin(request: Request) -> dict:
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise ApiError(403, "FORBIDDEN", "Faqat adminlar uchun.")
    return user


async def ensure_running():
    if (await db.get_setting("maintenance")) == "1":
        raise ApiError(503, "MAINTENANCE", "Texnik ishlar olib borilmoqda.")
