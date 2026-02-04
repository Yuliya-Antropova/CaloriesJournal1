from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.services.access import ensure_status


class DbUserMiddleware(BaseMiddleware):
    def __init__(self, db, cfg):
        self.db = db
        self.cfg = cfg

    async def __call__(self, handler, event: TelegramObject, data: dict):
        # Aiogram 3 кладёт пользователя/чат в data
        user = data.get("event_from_user")
        chat = data.get("event_chat")

        if user is None or chat is None:
            return await handler(event, data)

        tg_id = user.id
        chat_id = chat.id

        default_status = "trial"
        if tg_id in self.cfg.beta_whitelist:
            default_status = "beta"

        user_row = self.db.get_or_create_user(
            tg_id=tg_id,
            chat_id=chat_id,
            default_status=default_status
        )
        user_row = ensure_status(self.db, user_row)

        data["db"] = self.db
        data["user_row"] = user_row

        return await handler(event, data)
