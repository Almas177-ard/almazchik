"""Hamyon — yagona ishga tushirish nuqtasi.

Bot va WebApp bitta jarayonda, asyncio orqali parallel ishlaydi:

    python main.py

.env fayl to'ldirilgan bo'lishi kerak (namuna: .env.example).
"""
import asyncio
import logging

from dotenv import load_dotenv

load_dotenv()

import uvicorn  # noqa: E402

from app import db  # noqa: E402
from app.config import CFG  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
log = logging.getLogger("hamyon")


async def run_web():
    from app.web import create_app

    config = uvicorn.Config(
        create_app(), host=CFG.web_host, port=CFG.web_port, log_level="info"
    )
    server = uvicorn.Server(config)
    log.info("WebApp: http://%s:%s", CFG.web_host, CFG.web_port)
    await server.serve()


async def run_bot():
    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    from app.bot.handlers import router

    bot = Bot(token=CFG.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    log.info("Telegram bot ishga tushmoqda…")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def main():
    try:
        await db.init_db()
    except Exception as exc:
        log.error(
            "MySQL ga ulanib bo'lmadi: %s\n"
            "  1) MySQL serveri ishlayotganini tekshiring;\n"
            "  2) .env fayldagi DB_HOST / DB_PORT / DB_USER / DB_PASSWORD ni to'g'rilang.\n"
            "  (Baza va jadvallar avtomatik yaratiladi — qo'lda import qilish shart emas.)",
            exc,
        )
        return

    tasks = [asyncio.create_task(run_web(), name="web")]
    if CFG.bot_token:
        tasks.append(asyncio.create_task(run_bot(), name="bot"))
    else:
        log.warning("BOT_TOKEN kiritilmagan — faqat WebApp ishlaydi.")
    try:
        await asyncio.gather(*tasks)
    finally:
        await db.close_db()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("To'xtatildi.")
