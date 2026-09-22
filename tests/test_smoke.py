"""End-to-end smoke test: soxta MySQL (SQLite) + mock Partner API + FastAPI.

    cd almazchik && .venv/bin/python tests/test_smoke.py
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
import threading
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BOT_TOKEN = "7000000000:TEST_TOKEN_FOR_SIGNING"
os.environ["BOT_TOKEN"] = BOT_TOKEN
os.environ["WEBAPP_URL"] = "https://webapp.example"
os.environ["ADMIN_IDS"] = "555"
os.environ["SECRET_KEY"] = "test-secret"

# Soxta aiomysql ni haqiqiy modul o'rniga qo'yamiz
import fake_aiomysql  # noqa: E402
sys.modules["aiomysql"] = fake_aiomysql

from aiohttp import web  # noqa: E402
from mock_partner import build_app  # noqa: E402

PARTNER_PORT = 9911


def start_mock_partner():
    loop = asyncio.new_event_loop()

    def run():
        asyncio.set_event_loop(loop)

        async def _serve():
            runner = web.AppRunner(build_app())
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", PARTNER_PORT)
            await site.start()
            while True:
                await asyncio.sleep(3600)

        loop.run_until_complete(_serve())

    th = threading.Thread(target=run, daemon=True)
    th.start()
    time.sleep(0.8)


def make_init_data(user_id=555, first="Tester", username="tester", lang="uz"):
    user = {"id": user_id, "first_name": first, "username": username, "language_code": lang}
    params = {
        "auth_date": str(int(time.time())),
        "query_id": "AAFtest",
        "user": json.dumps(user, separators=(",", ":")),
    }
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode({**params, "hash": h})


PASSED, FAILED = 0, 0


def check(name, cond, extra=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  [ok] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} {extra}")


def main():
    start_mock_partner()

    from app import db
    from app.web import create_app
    from fastapi.testclient import TestClient

    async def setup():
        await db.init_db()
        await db.set_setting("partner_base_url", f"http://127.0.0.1:{PARTNER_PORT}/api/partner/v1")
        await db.set_setting("partner_api_key", "sk_live_TESTKEY")
        await db.set_setting("webapp_url", "https://webapp.example")
        await db.refresh_settings(force=True)

    LOOP = asyncio.new_event_loop()
    LOOP.run_until_complete(setup())

    app = create_app()
    anon = TestClient(app)
    tg = TestClient(app)
    adm = TestClient(app)

    print("== Statik sahifalar ==")
    r = anon.get("/")
    check("index.html", r.status_code == 200 and "Hamyon" in r.text)
    r = anon.get("/admin")
    check("admin.html", r.status_code == 200 and "adm.loginTitle" in r.text)
    r = anon.get("/css/soft.css")
    check("css", r.status_code == 200)
    r = anon.get("/img/logo.png")
    check("logo.png", r.status_code == 200)
    r = anon.get("/img/hero.png")
    check("hero.png", r.status_code == 200)

    print("== Autentifikatsiya ==")
    r = anon.get("/api/balance")
    check("auth yo'q → 401", r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED")
    r = anon.post("/api/auth", json={"initData": "hash=bad&auth_date=1"})
    check("yomon initData → 401", r.status_code == 401)
    r = anon.post("/api/auth", json={"initData": ""})
    check("bo'sh initData → 401", r.status_code == 401)

    r = tg.post("/api/auth", json={"initData": make_init_data()})
    check("initData qabul qilindi", r.status_code == 200 and r.json()["ok"] is True, r.text[:200])
    u = r.json()["user"]
    check("ADMIN_IDS → admin rol", u["role"] == "admin")
    check("public config", r.json()["public"]["appName"] == "Hamyon")

    r = tg.get("/api/me")
    check("GET /api/me", r.status_code == 200 and r.json()["user"]["id"] == 555)

    print("== Balans / katalog ==")
    r = tg.get("/api/balance")
    check("balance 125.50 USD", r.status_code == 200 and r.json()["balance"] == "125.50", r.text)
    r = tg.get("/api/providers")
    check("2 ta provayder", r.status_code == 200 and len(r.json()["data"]) == 2)
    r = tg.get("/api/products")
    check("2 ta mahsulot", r.status_code == 200 and len(r.json()["data"]) == 2)
    r = tg.get("/api/products?provider=gemini")
    check("provider filtri", r.status_code == 200 and len(r.json()["data"]) == 1)
    r = tg.get("/api/products/gemini-pro-monthly")
    check("mahsulot (slug)", r.status_code == 200 and r.json()["product"]["id"] == 42)
    r = tg.get("/api/products/51")
    check("mahsulot (id)", r.status_code == 200 and r.json()["product"]["slug"] == "capcut-pro-coupon")
    r = tg.get("/api/products/unknown-thing")
    check("not found product", r.status_code == 404 and r.json()["error"]["code"] == "PRODUCT_NOT_FOUND")

    print("== Buyurtmalar ==")
    r = tg.post("/api/orders", json={"productSlug": "gemini-pro-monthly", "quantity": 2})
    check("LINK buyurtma", r.status_code == 200 and r.json()["orderCode"], r.text[:200])
    code = r.json()["orderCode"]
    check("delivery.link", "link" in (r.json().get("delivery") or {}))
    check("balanceAfter mavjud", r.json().get("balanceAfter") == "100.50")

    r = tg.post("/api/orders", json={"productSlug": "capcut-pro-coupon", "quantity": 3})
    check("bulk buyurtma lines[]", r.status_code == 200 and len(r.json().get("lines", [])) == 3)
    check("bulk tier narx 8.00", r.json().get("unitPrice") == "8.00")

    r = tg.post("/api/orders", json={"productSlug": "gemini-pro-monthly", "quantity": 0})
    check("qty=0 rad etiladi", r.status_code == 400 and r.json()["error"]["code"] == "INVALID_QUANTITY")
    r = tg.post("/api/orders", json={"quantity": 1})
    check("refsiz so'rov rad etiladi", r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR")
    r = tg.post("/api/orders", json={"productSlug": "capcut-pro-coupon", "quantity": 99})
    check("katta qty rad etiladi", r.status_code == 400)

    r = tg.get("/api/orders")
    check("lokal buyurtmalar saqlangan", r.status_code == 200 and r.json()["meta"]["total"] == 2, r.text[:200])
    r = tg.get(f"/api/orders/{code}")
    check("buyurtma detail + delivery", r.status_code == 200 and "delivery" in r.json())

    r = tg.get("/api/usage")
    check("usage statistikasi", r.status_code == 200 and r.json().get("apiOrdersTotal") == 47)

    print("== Admin panel ==")
    r = anon.post("/admin/api/login", json={"password": "not-valid"})
    check("noto'g'ri parol → 401", r.status_code == 401)
    r = adm.post("/admin/api/login", json={"password": "admin123"})
    check("admin123 bilan kirish", r.status_code == 200)
    r = adm.get("/admin/api/me")
    check("admin sessiya", r.status_code == 200 and r.json()["role"] == "admin")

    r = adm.get("/admin/api/dashboard")
    d = r.json()
    check("dashboard stats", r.status_code == 200 and d["stats"]["usersTotal"] >= 1)
    check("dashboard API online", d["apiOnline"] is True)

    r = adm.get("/admin/api/settings")
    s = r.json()["settings"]
    check("API kalit niqoblangan", s["partner_api_key"].startswith("••••"), str(s))
    r = adm.get("/admin/api/settings?reveal=1")
    check("reveal=1 kalitni ko'rsatadi", r.json()["settings"]["partner_api_key"] == "sk_live_TESTKEY")

    r = adm.post("/admin/api/settings", json={"app_name": "TestDo'kon", "support_url": "https://t.me/help"})
    check("sozlamalar saqlandi", r.status_code == 200)
    r = anon.get("/api/public")
    check("app_name yangilandi", r.json()["public"]["appName"] == "TestDo'kon")
    # niqoblangan kalit saqlanmasin
    r = adm.post("/admin/api/settings", json={"partner_api_key": "••••TKEY"})
    r = adm.get("/admin/api/settings?reveal=1")
    check("niqoblangan kalit o'zgarmadi", r.json()["settings"]["partner_api_key"] == "sk_live_TESTKEY")

    print("== Maintenance ==")
    r = adm.post("/admin/api/settings", json={"maintenance": True})
    check("maintenance yoqildi", r.status_code == 200)
    r = tg.get("/api/balance")
    check("maintenance → 503", r.status_code == 503 and r.json()["error"]["code"] == "MAINTENANCE")
    r = adm.post("/admin/api/settings", json={"maintenance": "0"})
    r = tg.get("/api/balance")
    check("maintenance o'chdi", r.status_code == 200)

    print("== Foydalanuvchilar boshqaruvi ==")
    oddiy_client = TestClient(app)
    r = oddiy_client.post("/api/auth", json={"initData": make_init_data(user_id=777, first="Oddiy", username="oddiy")})
    check("oddiy user kirdi", r.status_code == 200 and r.json()["user"]["role"] == "user")
    r = adm.get("/admin/api/users?q=777")
    check("user qidiruvda topildi", r.status_code == 200 and r.json()["meta"]["total"] == 1)
    r = adm.post("/admin/api/users/777", json={"blocked": True})
    check("user bloklandi", r.status_code == 200 and r.json()["user"]["blocked"] == 1)
    r = oddiy_client.get("/api/me")
    check("sessiyada bloklangan user → 403", r.status_code == 403 and r.json()["error"]["code"] == "USER_BLOCKED")
    r = oddiy_client.post("/api/auth", json={"initData": make_init_data(user_id=777, first="Oddiy", username="oddiy")})
    check("bloklangan user qayta kira olmaydi", r.status_code == 403)
    r = adm.post("/admin/api/users/777", json={"blocked": False, "lang": "ru"})
    check("user blokdan olindi", r.status_code == 200 and r.json()["user"]["blocked"] == 0)
    r = adm.post("/admin/api/users/777", json={"role": "admin"})
    check("admin qilish", r.json()["user"]["role"] == "admin")

    print("== Katalog boshqaruvi ==")
    r = adm.get("/admin/api/catalog/products")
    check("admin katalog ro'yxati", r.status_code == 200 and len(r.json()["data"]) == 2)
    r = adm.post("/admin/api/catalog/products/capcut-pro-coupon/toggle", json={})
    check("mahsulot yashirildi", r.json()["blocked"] is True)
    r = tg.get("/api/products")
    check("yashirilgan mahsulot ko'rinmaydi", len(r.json()["data"]) == 1)
    r = adm.post("/admin/api/catalog/products/capcut-pro-coupon/toggle", json={})
    check("mahsulot qayta ochildi", r.json()["blocked"] is False)
    r = adm.post("/admin/api/catalog/sync")
    check("katalog sync", r.status_code == 200 and r.json()["products"] == 2)

    print("== Matnlar (tarjimalar) ==")
    r = adm.get("/admin/api/texts?lang=uz")
    keys = [x["key"] for x in r.json()["data"]]
    check("matn kalitlari", "welcome" in keys and "open_app" in keys)
    r = adm.post("/admin/api/texts", json={"key": "welcome", "lang": "uz", "value": "Yangi matn {name}!"})
    check("matn override saqlandi", r.status_code == 200 and r.json()["overridden"] is True)
    r = adm.get("/admin/api/texts?lang=uz")
    row = [x for x in r.json()["data"] if x["key"] == "welcome"][0]
    check("override ko'rinyapti", row["value"] == "Yangi matn {name}!" and row["overridden"])

    from app.i18n import get_text
    txt = LOOP.run_until_complete(get_text("welcome", "uz"))
    check("bot override ishlatadi", txt == "Yangi matn {name}!")
    txt = LOOP.run_until_complete(get_text("welcome", "ru"))
    check("boshqa til standartda qoladi", "Здравствуйте" in txt)

    print("== Rasmlar ==")
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d4944415478da63fcffff3f0300050001ff5acc590000000049454e44ae426082"
    )
    r = adm.post("/admin/api/images", files={"file": ("test.png", png, "image/png")})
    check("rasm yuklandi", r.status_code == 200 and r.json()["url"].startswith("/img/uploads/"), r.text[:200])
    img_id = r.json()["id"]
    r = anon.get(r.json()["url"])
    check("rasm fayli ochiq", r.status_code == 200)
    r = adm.get("/admin/api/images")
    check("rasmlar ro'yxati", len(r.json()["data"]) == 1)
    r = adm.post(f"/admin/api/images/{img_id}/use")
    check("start rasmi o'rnatildi", r.status_code == 200)
    r = anon.get("/api/public")
    check("public startPhoto yangi", r.json()["public"]["startPhoto"].startswith("/img/uploads/"))
    r = adm.delete(f"/admin/api/images/{img_id}")
    check("rasm o'chirildi", r.status_code == 200)

    print("== Parol ==")
    r = adm.post("/admin/api/password", json={"current": "wrong", "next": "secret123"})
    check("noto'g'ri joriy parol", r.status_code == 401)
    r = adm.post("/admin/api/password", json={"current": "admin123", "next": "secret123"})
    check("parol o'zgartirildi", r.status_code == 200)
    fresh = TestClient(app)
    r = fresh.post("/admin/api/login", json={"password": "admin123"})
    check("eski parol ishlamaydi", r.status_code == 401)
    r = fresh.post("/admin/api/login", json={"password": "secret123"})
    check("yangi parol ishlaydi", r.status_code == 200)

    print()
    print(f"Natija: {PASSED} o'tdi, {FAILED} yiqildi")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
