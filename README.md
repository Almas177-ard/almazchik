# Hamyon — Telegram bot + WebApp + Admin panel

Raqamli mahsulotlar do'koni: **Telegram bot** (WebApp ga kirish), **Soft UI** dizayndagi
**WebApp** (katalog, hamyon, buyurtmalar) va **to'liq admin panel**. Hammasi bitta
`python main.py` buyrug'i bilan ishga tushadi.

## Imkoniyatlar

- **Telegram bot** — `/start` bosilganda rasm + WebApp tugmasini yuboradi (boshqa xabar yo'q).
- **WebApp (Soft UI / neumorphism)** — to'q ko'k + och ko'k ranglar, **Tun/Kun** rejimi,
  3 til (**O'zbek / Русский / English**) — barcha matnlar tarjimasi bilan.
- **Partner API integratsiyasi** (`https://hamyon-api.uz/api/partner/v1` — paneldan o'zgartirish mumkin):
  balans, provayderlar, katalog, buyurtma berish (LINK / COUPON / READY_ACCOUNT),
  bulk (miqdorli) narxlar, statistika, idempotent buyurtmalar.
- **MySQL** — baza va jadvallar avtomatik yaratiladi.
- **Admin panel** (`/admin`) — hammasini boshqaradi:
  - Dashboard: statistika, API holati, texnik rejim (maintenance) tugmasi;
  - Sozlamalar: Partner API base URL va kaliti, ilova nomi, WebApp URL, til, kesh,
    to'ldirish rekvizitlari, parol almashtirish;
  - Foydalanuvchilar: qidiruv, bloklash, admin/user qilish;
  - Buyurtmalar: ro'yxat, qidiruv, yetkazish kontentini ko'rish;
  - Katalog: sinxronlash, mahsulotlarni yashirish/ko'rsatish;
  - Matnlar: bot matnlarini 3 tilda tahrirlash;
  - Rasmlar: yuklash, start rasmini tanlash.

## O'rnatish

1. **Python 3.10+** va **MySQL 8+** (yoki MariaDB 10.6+) kerak.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. `.env.example` dan `.env` nusxalang va to'ldiring:

```bash
cp .env.example .env
```

| Kalit | Tavsif |
|---|---|
| `BOT_TOKEN` | @BotFather dan olingan bot tokeni |
| `WEBAPP_URL` | WebApp ochiladigan **HTTPS** manzil (bot tugmasi shu yerga olib boradi) |
| `ADMIN_IDS` | Avtomatik admin bo'ladigan Telegram ID lar (vergul bilan) |
| `DB_HOST/PORT/USER/PASSWORD/NAME` | MySQL ulanish ma'lumotlari |
| `WEB_HOST/WEB_PORT` | Web server manzili (standart: 0.0.0.0:8000) |

3. Ishga tushirish:

```bash
python main.py
```

Bot ham, WebApp ham bitta jarayonda parallel ishlaydi. MySQL baza (`DB_NAME`) va
barcha jadvallar birinchi ishga tushirishda avtomatik yaratiladi.

## Muhim eslatmalar

- **WebApp faqat HTTPS da ochiladi.** Lokalda sinash uchun:
  `ngrok http 8000` yoki boshqa tunnel ishlatib, olingan manzilni `.env` dagi
  `WEBAPP_URL` ga va bot sozlamalariga yozing. Admin paneldan ham o'zgartirsa bo'ladi
  (Sozlamalar → WebApp URL).
- **Admin panel:** `/admin` sahifasi. Standart parol: **`admin123`** — birinchi kirishdayoq
  o'zgartiring (Sozlamalar → Xavfsizlik). Telegram orqali kirgan `ADMIN_IDS` dagi
  foydalanuvchilar panelga parolsiz ham kiradi.
- **Partner API kaliti:** Telegram botdagi API bo'limidan olingan `sk_live_...` kalitni
  admin panelga kiriting (Sozlamalar → Partner API).

## Admin panel bo'limlari

| Bo'lim | Nima qiladi |
|---|---|
| Boshqaruv | Umumiy statistika, API holati, maintenance yoqish/o'chirish, katalog sync |
| Sozlamalar | API base URL/kalit, ilova nomi, WebApp URL, til, kesh, depozit, parol |
| Foydalanuvchilar | Qidiruv, bloklash, rol berish |
| Buyurtmalar | Barcha API buyurtmalar + yetkazish kontenti |
| Katalog | API dan sinxronlash, mahsulot yashirish/ko'rsatish |
| Matnlar | Bot matnlari tarjimalari (uz/ru/en) |
| Rasmlar | Rasm yuklash, `/start` rasmini tanlash |

## Loyiha tuzilishi

```
main.py                 # hammasini ishga tushiradi (bot + web)
app/
  config.py             # .env sozlamalari
  db.py                 # MySQL pool, sxema, sozlamalar keshi
  i18n.py               # bot matnlari (uz/ru/en) + override
  users.py              # foydalanuvchi upsert
  partner/client.py     # Partner API HTTP mijozi
  bot/handlers.py       # /start → WebApp tugmasi
  web/
    auth.py             # initData tekshiruvi, session cookie
    catalog.py          # katalog keshi (TTL bilan)
    api.py              # WebApp API (balans, katalog, buyurtma…)
    admin_api.py        # Admin panel API
static/
  index.html            # WebApp (do'kon)
  admin.html            # Admin panel
  css/soft.css          # Soft UI dizayn tizimi
  js/core.js            # yordamchilar + i18n mexanizmi
  js/i18n.js            # barcha matnlar: uz / ru / en
  js/app.js             # do'kon mantig'i
  js/admin.js           # admin panel mantig'i
  img/                  # logo, hero, wallet (+ uploads/)
database/schema.sql     # MySQL sxemasi (ma'lumot uchun)
tests/                  # smoke test (soxta MySQL + mock Partner API)
```

## Testlar

MySQL serversiz ham to'liq HTTP oqimni tekshiruvchi smoke test:

```bash
.venv/bin/python tests/test_smoke.py
```

## Partner API haqida

Integratsiya Partner API v1 hujjatlariga muvofiq: `GET /health`, `GET /balance`,
`GET /catalog/providers`, `GET /catalog/products`, `POST /orders` (idempotent,
`externalOrderId` orqali), `GET /orders`, `GET /usage`. Buyurtmalar LINK / COUPON /
READY_ACCOUNT yetkazib berish turlarini qo'llab-quvvatlaydi; bulk buyurtmalar `lines[]`
qaytaradi. Xato kodlari (`INSUFFICIENT_BALANCE`, `OUT_OF_STOCK`, `RATE_LIMIT_EXCEEDED`,
`MAINTENANCE`…) foydalanuvchiga o'z tilida ko'rsatiladi.
