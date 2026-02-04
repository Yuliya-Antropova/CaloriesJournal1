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
        data["db"] = self.db
        data["beta_whitelist"] = self.beta_whitelist
        data["cfg"] = self.cfg

        if hasattr(event, "from_user") and event.from_user:
            default_status = "beta" if event.from_user.id in self.beta_whitelist else "trial"
            event.from_user.default_status = default_status  # type: ignore[attr-defined]
            chat_id = getattr(getattr(event, "chat", None), "id", 0) or getattr(getattr(event, "message", None), "chat", None).id if getattr(event, "message", None) else 0
            user_row = self.db.get_or_create_user(event.from_user.id, chat_id or 0, default_status)
            event.from_user.id_db = user_row.id  # type: ignore[attr-defined]

        return await handler(event, data)
