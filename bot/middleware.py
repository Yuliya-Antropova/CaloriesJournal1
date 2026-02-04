from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any
from bot.db import DB

class DBMiddleware(BaseMiddleware):
    def __init__(self, db: DB, beta_whitelist: set[int], cfg):
        super().__init__()
        self.db = db
        self.beta_whitelist = beta_whitelist
        self.cfg = cfg

    async def __call__(self, handler: Callable, event: TelegramObject, data: Dict[str, Any]) -> Any:
        # Inject common deps
        data["db"] = self.db
        data["beta_whitelist"] = self.beta_whitelist
        data["cfg"] = self.cfg

        # Prepare per-user context WITHOUT mutating aiogram User (it is frozen / pydantic model)
        from_user = getattr(event, "from_user", None)
        if from_user:
            default_status = "beta" if from_user.id in self.beta_whitelist else "trial"

            chat_obj = getattr(event, "chat", None)
            if chat_obj and getattr(chat_obj, "id", None):
                chat_id = chat_obj.id
            else:
                msg = getattr(event, "message", None)
                chat_id = getattr(getattr(msg, "chat", None), "id", 0) if msg else 0

            user_row = self.db.get_or_create_user(from_user.id, int(chat_id or 0), default_status)

            data["user_row"] = user_row
            data["user_id"] = user_row.id
            data["default_status"] = default_status

        return await handler(event, data)
