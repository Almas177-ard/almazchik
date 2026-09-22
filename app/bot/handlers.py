"""Bot handlerlari.

Talabga ko'ra bot faqat /start bosilganda WebApp ga kirish tugmasini yuboradi.
Boshqa xabarlarga qisqa yo'naltiruvchi matn javob bo'ladi.
"""
import html
import logging
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from app import db
from app.config import CFG, STATIC_DIR
from app.i18n import get_text
from app.users import upsert_user

log = logging.getLogger("hamyon.bot")
router = Router(name="main")


async def _webapp_keyboard(lang: str):
    webapp_url = (await db.get_setting("webapp_url")) or CFG.webapp_url
    label = await get_text("open_app", lang)
    if not webapp_url:
        return None
    if webapp_url.startswith("https://"):
        button = InlineKeyboardButton(text=label, web_app=WebAppInfo(url=webapp_url))
    else:
        # WebApp faqat HTTPS da ishlaydi; vaqtincha oddiy havola sifatida
        button = InlineKeyboardButton(text=label, url=webapp_url)
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


@router.message(CommandStart())
async def cmd_start(message: Message):
    tg = message.from_user
    if tg is None:
        return
    user = await upsert_user(
        tg.id, username=tg.username, first_name=tg.first_name, last_name=tg.last_name
    )
    lang = user.get("lang") or "uz"

    if user.get("blocked"):
        await message.answer(await get_text("blocked", lang))
        return
    if (await db.get_setting("maintenance")) == "1":
        await message.answer(await get_text("maintenance", lang))
        return

    name = html.escape(tg.first_name or tg.username or "")
    caption = (await get_text("welcome", lang)).replace("{name}", name)
    kb = await _webapp_keyboard(lang)

    photo_rel = await db.get_setting("start_photo", "img/hero.png")
    photo_path = (STATIC_DIR / photo_rel).resolve() if photo_rel else None
    if photo_path and str(photo_path).startswith(str(STATIC_DIR)) and photo_path.is_file():
        try:
            await message.answer_photo(
                photo=FSInputFile(photo_path), caption=caption, reply_markup=kb
            )
            return
        except Exception as exc:  # rasm yuborilmasa matnga o'tamiz
            log.warning("Rasm yuborilmadi: %s", exc)
    await message.answer(caption, reply_markup=kb, disable_web_page_preview=True)


@router.message()
async def fallback(message: Message):
    tg = message.from_user
    lang = "uz"
    if tg is not None:
        user = await db.fetch_one("SELECT lang FROM users WHERE tg_id=%s", (tg.id,))
        if user:
            lang = user.get("lang") or "uz"
    try:
        await message.answer(await get_text("fallback", lang))
    except Exception:
        pass
