"""Partner API ning mock serveri (test uchun)."""
import json

from aiohttp import web

PRODUCTS = [
    {
        "id": 42,
        "slug": "gemini-pro-monthly",
        "productCode": "GEM-PRO-30",
        "name": "Gemini Pro — 30 days",
        "provider": {"id": 3, "key": "gemini", "name": "Gemini",
                     "emoji": {"normal": "✨", "customTelegramId": None, "display": "✨ Gemini"}},
        "emoji": {"normal": "✨", "customTelegramId": None, "display": "✨ Gemini Pro"},
        "deliveryType": "LINK",
        "sortOrder": 1,
        "catalogPrice": "15.00",
        "yourPrice": "12.50",
        "currency": "USD",
        "durationDays": 30,
        "warranty": {"enabled": True, "days": 7},
        "stock": {"inStock": True, "count": 48, "maxQuantity": 48},
        "bulkDiscount": {
            "enabled": True,
            "stackingPolicy": "BEST_PRICE",
            "tiers": [
                {"minQuantity": 5, "maxQuantity": 9, "unitPrice": "11.50"},
                {"minQuantity": 10, "maxQuantity": None, "unitPrice": "10.00"},
            ],
        },
        "pricing": {"catalogPrice": "15.00", "yourUnitPrice": "12.50",
                    "loyaltyApplied": True, "campaignApplied": False},
        "flags": {"sensitiveDelivery": False, "hasInstructions": True, "instantDelivery": True},
        "description": "Instant Gemini Pro activation link.",
        "instructions": "Open the link and sign in.",
    },
    {
        "id": 51,
        "slug": "capcut-pro-coupon",
        "productCode": "CAP-PRO",
        "name": "CapCut Pro Coupon",
        "provider": {"id": 4, "key": "capcut", "name": "CapCut",
                     "emoji": {"normal": "🎬", "customTelegramId": None, "display": "🎬 CapCut"}},
        "emoji": {"normal": "🎬", "customTelegramId": None, "display": "🎬 CapCut"},
        "deliveryType": "COUPON",
        "sortOrder": 2,
        "catalogPrice": "9.00",
        "yourPrice": "8.00",
        "currency": "USD",
        "durationDays": None,
        "warranty": {"enabled": False, "days": 0},
        "stock": {"inStock": True, "count": 5, "maxQuantity": 5},
        "bulkDiscount": {"enabled": False, "tiers": []},
        "pricing": {"catalogPrice": "9.00", "yourUnitPrice": "8.00",
                    "loyaltyApplied": False, "campaignApplied": False},
        "flags": {"sensitiveDelivery": False, "hasInstructions": False, "instantDelivery": True},
    },
]

ORDERS = {}
_seq = [0]


def build_app() -> web.Application:
    app = web.Application()

    def auth_ok(request):
        h = request.headers.get("Authorization", "")
        return h == "Bearer sk_live_TESTKEY"

    async def health(request):
        return web.json_response({"ok": True, "service": "partner-api", "version": 1})

    async def balance(request):
        if not auth_ok(request):
            return web.json_response(
                {"ok": False, "error": {"code": "INVALID_API_KEY", "message": "Missing API key.", "requestId": "req_x"}},
                status=401)
        return web.json_response({"ok": True, "balance": "125.50", "currency": "USD"})

    async def usage(request):
        if not auth_ok(request):
            return web.json_response({"ok": False, "error": {"code": "INVALID_API_KEY", "message": "x"}}, status=401)
        return web.json_response({
            "balance": "125.50", "currency": "USD", "apiOrdersTotal": 47,
            "apiSpendTotal": "582.30", "apiOrders24h": 5, "apiSpend24h": "62.50",
            "requestCountToday": 128, "errorCountToday": 3})

    async def providers(request):
        if not auth_ok(request):
            return web.json_response({"ok": False, "error": {"code": "INVALID_API_KEY", "message": "x"}}, status=401)
        return web.json_response({"data": [
            {"id": 3, "key": "gemini", "name": "Gemini", "sortOrder": 10,
             "emoji": {"normal": "✨", "customTelegramId": None, "display": "✨ Gemini"}},
            {"id": 4, "key": "capcut", "name": "CapCut", "sortOrder": 20,
             "emoji": {"normal": "🎬", "customTelegramId": None, "display": "🎬 CapCut"}},
        ]})

    async def products(request):
        if not auth_ok(request):
            return web.json_response({"ok": False, "error": {"code": "INVALID_API_KEY", "message": "x"}}, status=401)
        prov = request.query.get("provider")
        data = PRODUCTS if not prov else [p for p in PRODUCTS if p["provider"]["key"] == prov]
        return web.json_response({"data": data})

    async def product_detail(request):
        if not auth_ok(request):
            return web.json_response({"ok": False, "error": {"code": "INVALID_API_KEY", "message": "x"}}, status=401)
        ref = request.match_info["ref"]
        for p in PRODUCTS:
            if p["slug"] == ref or str(p["id"]) == ref:
                return web.json_response(p)
        return web.json_response(
            {"ok": False, "error": {"code": "PRODUCT_NOT_FOUND", "message": "Unknown product.", "requestId": "req_p"}},
            status=404)

    async def create_order(request):
        if not auth_ok(request):
            return web.json_response({"ok": False, "error": {"code": "INVALID_API_KEY", "message": "x"}}, status=401)
        body = await request.json()
        slug = body.get("productSlug")
        qty = int(body.get("quantity", 1))
        ext = body.get("externalOrderId")
        prod = next((p for p in PRODUCTS if p["slug"] == slug), None)
        if not prod:
            return web.json_response(
                {"ok": False, "error": {"code": "PRODUCT_NOT_FOUND", "message": "Unknown product."}}, status=404)
        if prod["stock"]["count"] < qty:
            return web.json_response(
                {"ok": False, "error": {"code": "OUT_OF_STOCK", "message": "Product is out of stock."}}, status=400)
        # idempotentlik: bir xil externalOrderId → bir xil buyurtma
        for oc, o in ORDERS.items():
            if o["externalOrderId"] == ext:
                resp = dict(o)
                resp.pop("balanceAfter", None)
                return web.json_response(resp)
        unit = float(prod["yourPrice"])
        if prod["bulkDiscount"]["enabled"]:
            for tr in prod["bulkDiscount"]["tiers"]:
                mx = tr["maxQuantity"] if tr["maxQuantity"] is not None else 10**9
                if tr["minQuantity"] <= qty <= mx:
                    unit = float(tr["unitPrice"])
        total = round(unit * qty, 2)
        _seq[0] += 1
        code = f"SO-TEST-{_seq[0]:04d}"
        resp = {
            "ok": True,
            "orderCode": code,
            "externalOrderId": ext,
            "status": "COMPLETED",
            "deliveryType": prod["deliveryType"],
            "product": {"slug": prod["slug"], "name": prod["name"], "productCode": prod["productCode"]},
            "quantity": qty,
            "unitPrice": f"{unit:.2f}",
            "totalCharged": f"{total:.2f}",
            "currency": "USD",
            "balanceAfter": f"{125.5 - total:.2f}",
            "createdAt": "2026-09-22T10:00:00.000Z",
        }
        if prod["deliveryType"] == "LINK":
            resp["delivery"] = {"link": "https://example.com/activate/xyz123",
                                "instructions": "Open the link and sign in."}
        elif qty > 1:
            resp["lines"] = [
                {"orderCode": f"{code}-L{i}", "code": f"COUPON-{i:03d}"} for i in range(1, qty + 1)
            ]
        else:
            resp["delivery"] = {"code": "CAPCUT-TEST-CODE", "instructions": "Redeem within 24 hours."}
        ORDERS[code] = dict(resp)
        return web.json_response(resp)

    async def orders_list(request):
        if not auth_ok(request):
            return web.json_response({"ok": False, "error": {"code": "INVALID_API_KEY", "message": "x"}}, status=401)
        return web.json_response({"data": list(ORDERS.values()),
                                  "meta": {"page": 1, "limit": 20, "total": len(ORDERS), "totalPages": 1}})

    async def order_detail(request):
        if not auth_ok(request):
            return web.json_response({"ok": False, "error": {"code": "INVALID_API_KEY", "message": "x"}}, status=401)
        code = request.match_info["code"]
        if code in ORDERS:
            return web.json_response(ORDERS[code])
        return web.json_response(
            {"ok": False, "error": {"code": "ORDER_NOT_FOUND", "message": "Unknown order."}}, status=404)

    app.router.add_get("/api/partner/v1/health", health)
    app.router.add_get("/api/partner/v1/balance", balance)
    app.router.add_get("/api/partner/v1/usage", usage)
    app.router.add_get("/api/partner/v1/catalog/providers", providers)
    app.router.add_get("/api/partner/v1/catalog/products", products)
    app.router.add_get("/api/partner/v1/catalog/products/{ref}", product_detail)
    app.router.add_post("/api/partner/v1/orders", create_order)
    app.router.add_get("/api/partner/v1/orders", orders_list)
    app.router.add_get("/api/partner/v1/orders/{code}", order_detail)
    return app


if __name__ == "__main__":
    web.run_app(build_app(), host="127.0.0.1", port=9911)
