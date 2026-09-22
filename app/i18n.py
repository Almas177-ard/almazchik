"""Bot matnlari — 3 til (uz / ru / en). Panel orqali tahrirlash mumkin (texts jadvali)."""
from app import db

SUPPORTED_LANGS = ("uz", "ru", "en")

DEFAULT_TEXTS = {
    "welcome": {
        "uz": "Assalomu alaykum, {name}!\n\nHamyon do'koniga xush kelibsiz — raqamli mahsulotlar, aktivatsiya havolalari va tayyor akkauntlar bir necha soniyada yetkaziladi.\n\nIlovani ochish uchun quyidagi tugmani bosing.",
        "ru": "Здравствуйте, {name}!\n\nДобро пожаловать в магазин Hamyon — цифровые товары, ссылки активации и готовые аккаунты с мгновенной доставкой.\n\nНажмите кнопку ниже, чтобы открыть приложение.",
        "en": "Hello, {name}!\n\nWelcome to Hamyon store — digital goods, activation links and ready accounts with instant delivery.\n\nTap the button below to open the app.",
    },
    "open_app": {
        "uz": "Ilovani ochish",
        "ru": "Открыть приложение",
        "en": "Open the app",
    },
    "fallback": {
        "uz": "Bu bot faqat ilovaga olib kiradi. Iltimos, /start buyrug'ini yuboring va ilovani oching.",
        "ru": "Этот бот только открывает приложение. Отправьте /start и откройте приложение.",
        "en": "This bot only opens the app. Please send /start and open the app.",
    },
    "blocked": {
        "uz": "Kechirasiz, sizning hisobingiz bloklangan. Yordam uchun qo'llab-quvvatlash xizmatiga murojaat qiling.",
        "ru": "Извините, ваш аккаунт заблокирован. Обратитесь в службу поддержки.",
        "en": "Sorry, your account is blocked. Please contact support.",
    },
    "maintenance": {
        "uz": "Hozirda texnik ishlar olib borilmoqda. Iltimos, birozdan so'ng qayta urinib ko'ring.",
        "ru": "Сейчас ведутся технические работы. Попробуйте ещё раз чуть позже.",
        "en": "We are under maintenance right now. Please try again in a few minutes.",
    },
}


def text_keys():
    return sorted(DEFAULT_TEXTS.keys())


def default_text(key: str, lang: str) -> str:
    block = DEFAULT_TEXTS.get(key, {})
    if lang not in SUPPORTED_LANGS:
        lang = "uz"
    return block.get(lang) or block.get("uz", "") or key


async def get_text(key: str, lang: str) -> str:
    """Avval paneldagi override ni, bo'lmasa standart matnni qaytaradi."""
    if lang not in SUPPORTED_LANGS:
        lang = "uz"
    row = await db.fetch_one("SELECT value FROM texts WHERE tkey=%s AND lang=%s", (key, lang))
    if row and row["value"] and row["value"].strip():
        return row["value"]
    return default_text(key, lang)
