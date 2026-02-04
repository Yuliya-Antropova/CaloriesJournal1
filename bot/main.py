import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import load_config
from bot.db import DB
from bot.middleware import DBMiddleware
from bot.handlers.start import router as start_router
from bot.handlers.food import router as food_router
from bot.handlers.misc import router as misc_router
from bot.handlers.payments import router as payments_router

async def main():
    cfg = load_config()
    db = DB(cfg.db_path)

    bot = Bot(token=cfg.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    mw = DBMiddleware(db, cfg.beta_whitelist, cfg)
    dp.message.middleware(mw)
    dp.callback_query.middleware(mw)
    dp.pre_checkout_query.middleware(mw)

    dp.include_router(start_router)
    dp.include_router(misc_router)
    dp.include_router(payments_router)
    dp.include_router(food_router)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
