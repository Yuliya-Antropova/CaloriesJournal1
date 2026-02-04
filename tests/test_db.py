from bot.db import DB
from datetime import datetime
import os, tempfile

def test_db_flow():
    with tempfile.TemporaryDirectory() as td:
        db = DB(os.path.join(td, "t.db"))
        u = db.get_or_create_user(1, 10, "trial")
        assert u.tg_id == 1
        db.upsert_profile(u.id, sex="f", age=30, height_cm=165, weight_kg=60, activity="light", goal="maintain", palm_len_cm=None, palm_w_cm=None)
        db.upsert_targets(u.id, 2000, 100, 25)
        db.add_food_entry(u.id, datetime.utcnow().replace(microsecond=0).isoformat(), "coffee", None, "{}", 10, 30, 20, 0.5, 0.1, 0.2)
        low, mid, high = db.today_kcal_sum(u.id, datetime.utcnow())
        assert mid >= 20
        db.close()
