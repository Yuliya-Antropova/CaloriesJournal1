import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from bot.config import load_config
from bot.db import DB
from bot.middleware import DbUserMiddleware

from bot.handlers.start import router as start_router
from bot.handlers.food import router as food_router
from bot.handlers.misc import router as misc_router
from bot.handlers.payments import router as payments_router


async def main():
    cfg = load_config()

    db = DB(cfg.db_path)

    bot = Bot(token=cfg.bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    # Middleware injects db and user_row into handler kwargs
    dp.update.middleware(DbUserMiddleware(db=db, cfg=cfg))

    dp.include_router(start_router)
    dp.include_router(food_router)
    dp.include_router(misc_router)
    dp.include_router(payments_router)

    # Important for polling mode (no webhook)
    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
