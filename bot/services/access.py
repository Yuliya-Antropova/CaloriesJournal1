from __future__ import annotations
from datetime import datetime
from bot.db import DB, UserRow

def is_active(user: UserRow) -> bool:
    if user.status == "beta":
        return True
    now = datetime.utcnow()
    if user.status == "active":
        if user.paid_until:
            return datetime.fromisoformat(user.paid_until) > now
        return True
    if user.status == "trial":
        if user.trial_end:
            return datetime.fromisoformat(user.trial_end) > now
        return False
    return False

def ensure_status(db: DB, user: UserRow) -> UserRow:
    # move trial->expired if needed
    if user.status == "trial" and user.trial_end:
        if datetime.fromisoformat(user.trial_end) <= datetime.utcnow():
            db.conn.execute("UPDATE users SET status='expired' WHERE id=?", (user.id,))
            db.conn.commit()
            return db.get_or_create_user(user.tg_id, user.chat_id, user.status)
    return user
