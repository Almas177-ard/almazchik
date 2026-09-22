"""Partner API v1 HTTP mijozi.

Base URL va API kaliti admin panel sozlamalaridan o'qiladi, shuning uchun
paneldan o'zgartirilsa darhol kuchga kiradi.
"""
import logging

import aiohttp

from app import db

log = logging.getLogger("hamyon.partner")


class PartnerError(Exception):
    """Partner API tomonidan qaytarilgan xato (kod + xabar + HTTP status)."""

    def __init__(self, code: str, message: str, status: int = 400, extra=None, request_id=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}
        self.request_id = request_id


async def _request(method: str, path: str, *, auth: bool = True, params=None,
                   json_body=None, timeout: int = 45):
    base = ((await db.get_setting("partner_base_url")) or "").strip().rstrip("/")
    if not base:
        raise PartnerError(
            "API_NOT_CONFIGURED",
            "Partner API manzili sozlanmagan. Admin paneldan base URL kiriting.",
            503,
        )
    headers = {"Accept": "application/json"}
    if auth:
        key = (await db.get_setting("partner_api_key") or "").strip()
        if not key:
            raise PartnerError(
                "API_NOT_CONFIGURED",
                "Partner API kaliti sozlanmagan. Admin paneldan API kalitini kiriting.",
                503,
            )
        headers["Authorization"] = f"Bearer {key}"

    url = base + path
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = None

                is_error = resp.status >= 400 or (
                    isinstance(data, dict) and data.get("ok") is False
                )
                if is_error:
                    err = {}
                    if isinstance(data, dict):
                        err = data.get("error") or {}
                        if isinstance(err, str):
                            err = {"message": err}
                    code = err.get("code") or (
                        "MAINTENANCE" if resp.status == 503 else "PARTNER_ERROR"
                    )
                    message = err.get("message") or f"Partner API xatosi (HTTP {resp.status})"
                    extra = {
                        k: v for k, v in err.items() if k not in ("code", "message", "requestId")
                    }
                    raise PartnerError(code, message, resp.status, extra, err.get("requestId"))
                return data if data is not None else {}
    except aiohttp.ClientError as exc:
        log.warning("Partner API tarmoq xatosi: %s", exc)
        raise PartnerError("PARTNER_NETWORK", f"Partner API ga ulanib bo'lmadi: {exc}", 502)


# ------------------------------------------------------------------ Endpointlar
async def health() -> dict:
    return await _request("GET", "/health", auth=False, timeout=15)


async def balance() -> dict:
    return await _request("GET", "/balance")


async def usage() -> dict:
    return await _request("GET", "/usage")


async def providers() -> list:
    data = await _request("GET", "/catalog/providers")
    return data.get("data", []) if isinstance(data, dict) else []


async def products(provider: str = None) -> list:
    params = {"provider": provider} if provider else None
    data = await _request("GET", "/catalog/products", params=params)
    return data.get("data", []) if isinstance(data, dict) else []


async def product(ref) -> dict:
    return await _request("GET", f"/catalog/products/{ref}")


async def create_order(payload: dict) -> dict:
    return await _request("POST", "/orders", json_body=payload, timeout=60)


async def list_orders(params: dict = None) -> dict:
    return await _request("GET", "/orders", params=params)


async def order_detail(order_code: str) -> dict:
    return await _request("GET", f"/orders/{order_code}")
