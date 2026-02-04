from __future__ import annotations
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id INTEGER NOT NULL UNIQUE,
  chat_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'trial',         -- beta|trial|active|expired
  trial_start TEXT,
  trial_end TEXT,
  paid_until TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
  user_id INTEGER PRIMARY KEY,
  sex TEXT NOT NULL,                           -- f|m
  age INTEGER NOT NULL,
  height_cm REAL NOT NULL,
  weight_kg REAL NOT NULL,
  activity TEXT NOT NULL,                      -- sedentary|light|moderate|high|athlete
  goal TEXT NOT NULL,                          -- lose|maintain|gain
  palm_len_cm REAL,                            -- optional
  palm_w_cm REAL,                              -- optional
  updated_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS daily_targets (
  user_id INTEGER PRIMARY KEY,
  kcal_target INTEGER NOT NULL,
  protein_g INTEGER NOT NULL,
  fiber_g INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS food_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  ts TEXT NOT NULL,
  text TEXT,
  photo_file_id TEXT,
  parsed_json TEXT NOT NULL,
  kcal_low INTEGER NOT NULL,
  kcal_high INTEGER NOT NULL,
  kcal_mid INTEGER NOT NULL,
  conf REAL NOT NULL,
  err_low REAL NOT NULL,
  err_high REAL NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS promo_codes (
  user_id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS referrals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  referrer_user_id INTEGER NOT NULL,
  referred_user_id INTEGER NOT NULL UNIQUE,
  code TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'invited',       -- invited|discount_reserved|paid|rewarded
  created_at TEXT NOT NULL,
  first_payment_at TEXT,
  FOREIGN KEY(referrer_user_id) REFERENCES users(id),
  FOREIGN KEY(referred_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS reward_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  days INTEGER NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_meta (
  user_id INTEGER NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, key),
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

@dataclass
class UserRow:
    id: int
    tg_id: int
    chat_id: int
    status: str
    trial_start: Optional[str]
    trial_end: Optional[str]
    paid_until: Optional[str]

class DB:
    def __init__(self, path: str):
        self.path = (path or "bot.db").strip()

        # If DB_PATH points to a directory that doesn't exist (e.g. /data/bot.db),
        # create the directory to prevent sqlite "unable to open database file".
        dirn = os.path.dirname(self.path)
        if dirn and not os.path.exists(dirn):
            os.makedirs(dirn, exist_ok=True)

        try:
            self.conn = sqlite3.connect(self.path)
        except sqlite3.OperationalError as e:
            raise sqlite3.OperationalError(
                f"unable to open database file: path='{self.path}'. "
                f"Fix: set DB_PATH to a writable path (e.g. /data/bot.db) and mount Railway Volume to /data."
            ) from e

        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def now_iso(self) -> str:
        return datetime.utcnow().replace(microsecond=0).isoformat()

    def get_or_create_user(self, tg_id: int, chat_id: int, default_status: str) -> UserRow:
        cur = self.conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
        row = cur.fetchone()
        if row:
            if row["chat_id"] != chat_id and chat_id:
                self.conn.execute("UPDATE users SET chat_id=? WHERE tg_id=?", (chat_id, tg_id))
                self.conn.commit()
            return UserRow(
                id=row["id"], tg_id=row["tg_id"], chat_id=row["chat_id"],
                status=row["status"], trial_start=row["trial_start"], trial_end=row["trial_end"], paid_until=row["paid_until"]
            )

        now = self.now_iso()
        trial_start = now
        trial_end = (datetime.utcnow() + timedelta(days=3)).replace(microsecond=0).isoformat()
        status = default_status
        if status == "beta":
            trial_start = None
            trial_end = None

        self.conn.execute(
            "INSERT INTO users (tg_id, chat_id, created_at, status, trial_start, trial_end) VALUES (?,?,?,?,?,?)",
            (tg_id, chat_id, now, status, trial_start, trial_end),
        )
        self.conn.commit()
        return self.get_or_create_user(tg_id, chat_id, default_status)

    def set_user_status(self, user_id: int, status: str):
        self.conn.execute("UPDATE users SET status=? WHERE id=?", (status, user_id))
        self.conn.commit()

    def set_paid_until(self, user_id: int, paid_until_iso: str):
        self.conn.execute("UPDATE users SET paid_until=?, status='active' WHERE id=?", (paid_until_iso, user_id))
        self.conn.commit()

    def upsert_profile(self, user_id: int, **fields):
        cols = ["sex","age","height_cm","weight_kg","activity","goal","palm_len_cm","palm_w_cm","updated_at"]
        values = [fields.get(c) for c in cols[:-1]] + [self.now_iso()]
        existing = self.conn.execute("SELECT 1 FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        if existing:
            set_sql = ", ".join([f"{c}=?" for c in cols[:-1]] + ["updated_at=?"])
            self.conn.execute(f"UPDATE profiles SET {set_sql} WHERE user_id=?", (*values, user_id))
        else:
            self.conn.execute(
                f"INSERT INTO profiles (user_id, {','.join(cols)}) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (user_id, *values),
            )
        self.conn.commit()

    def get_profile(self, user_id: int) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def upsert_targets(self, user_id: int, kcal_target: int, protein_g: int, fiber_g: int):
        now = self.now_iso()
        existing = self.conn.execute("SELECT 1 FROM daily_targets WHERE user_id=?", (user_id,)).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE daily_targets SET kcal_target=?, protein_g=?, fiber_g=?, updated_at=? WHERE user_id=?",
                (kcal_target, protein_g, fiber_g, now, user_id),
            )
        else:
            self.conn.execute(
                "INSERT INTO daily_targets (user_id, kcal_target, protein_g, fiber_g, updated_at) VALUES (?,?,?,?,?)",
                (user_id, kcal_target, protein_g, fiber_g, now),
            )
        self.conn.commit()

    def get_targets(self, user_id: int) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM daily_targets WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def add_food_entry(self, user_id: int, ts_iso: str, text: str | None, photo_file_id: str | None,
                       parsed_json: str, kcal_low: int, kcal_high: int, kcal_mid: int,
                       conf: float, err_low: float, err_high: float) -> int:
        cur = self.conn.execute(
            """INSERT INTO food_entries
                (user_id, ts, text, photo_file_id, parsed_json, kcal_low, kcal_high, kcal_mid, conf, err_low, err_high)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, ts_iso, text, photo_file_id, parsed_json, kcal_low, kcal_high, kcal_mid, conf, err_low, err_high),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_food_entry(self, entry_id: int, user_id: int) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM food_entries WHERE id=? AND user_id=?", (entry_id, user_id)).fetchone()
        return dict(row) if row else None

    def update_food_entry(self, entry_id: int, user_id: int, parsed_json: str,
                          kcal_low: int, kcal_high: int, kcal_mid: int, conf: float, err_low: float, err_high: float):
        self.conn.execute(
            """UPDATE food_entries
               SET parsed_json=?, kcal_low=?, kcal_high=?, kcal_mid=?, conf=?, err_low=?, err_high=?
               WHERE id=? AND user_id=?""",
            (parsed_json, kcal_low, kcal_high, kcal_mid, conf, err_low, err_high, entry_id, user_id)
        )
        self.conn.commit()

    def today_kcal_sum(self, user_id: int, day_utc: datetime) -> tuple[int,int,int]:
        start = day_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        rows = self.conn.execute(
            "SELECT SUM(kcal_low) as a, SUM(kcal_mid) as b, SUM(kcal_high) as c FROM food_entries WHERE user_id=? AND ts>=? AND ts<?",
            (user_id, start.isoformat(), end.isoformat()),
        ).fetchone()
        a = int(rows["a"] or 0)
        b = int(rows["b"] or 0)
        c = int(rows["c"] or 0)
        return a,b,c

    def get_meta(self, user_id: int, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM user_meta WHERE user_id=? AND key=?", (user_id, key)).fetchone()
        return row["value"] if row else None

    def set_meta(self, user_id: int, key: str, value: str):
        now = self.now_iso()
        existing = self.conn.execute("SELECT 1 FROM user_meta WHERE user_id=? AND key=?", (user_id, key)).fetchone()
        if existing:
            self.conn.execute("UPDATE user_meta SET value=?, updated_at=? WHERE user_id=? AND key=?", (value, now, user_id, key))
        else:
            self.conn.execute("INSERT INTO user_meta (user_id, key, value, updated_at) VALUES (?,?,?,?)", (user_id, key, value, now))
        self.conn.commit()

    def get_or_create_promo_code(self, user_id: int) -> str:
        row = self.conn.execute("SELECT code FROM promo_codes WHERE user_id=?", (user_id,)).fetchone()
        if row:
            return row["code"]
        import secrets, string
        alphabet = string.ascii_uppercase + string.digits
        code = "NIGMA-" + "".join(secrets.choice(alphabet) for _ in range(6))
        self.conn.execute("INSERT INTO promo_codes (user_id, code, created_at) VALUES (?,?,?)",
                          (user_id, code, self.now_iso()))
        self.conn.commit()
        return code

    def apply_promo_for_new_user(self, referred_user_id: int, code: str) -> tuple[bool,str, int | None]:
        existing = self.conn.execute("SELECT 1 FROM referrals WHERE referred_user_id=?", (referred_user_id,)).fetchone()
        if existing:
            return False, "Промокод уже применён ранее.", None

        owner = self.conn.execute("SELECT user_id FROM promo_codes WHERE code=?", (code,)).fetchone()
        if not owner:
            return False, "Промокод не найден.", None
        referrer_user_id = int(owner["user_id"])
        if referrer_user_id == referred_user_id:
            return False, "Нельзя применить свой промокод.", None

        self.conn.execute(
            "INSERT INTO referrals (referrer_user_id, referred_user_id, code, status, created_at) VALUES (?,?,?,?,?)",
            (referrer_user_id, referred_user_id, code, "discount_reserved", self.now_iso()),
        )
        self.conn.commit()
        return True, "Ок. Скидка будет применена при первой оплате после триала.", referrer_user_id

    def get_discount_for_user(self, user_id: int) -> int:
        row = self.conn.execute(
            "SELECT status FROM referrals WHERE referred_user_id=?",
            (user_id,)
        ).fetchone()
        if row and row["status"] == "discount_reserved":
            return 1
        return 0

    def mark_first_payment(self, referred_user_id: int):
        self.conn.execute(
            "UPDATE referrals SET status='paid', first_payment_at=? WHERE referred_user_id=? AND status='discount_reserved'",
            (self.now_iso(), referred_user_id),
        )
        self.conn.commit()

    def reward_referrer_if_paid(self, referred_user_id: int, days: int = 7) -> Optional[int]:
        row = self.conn.execute(
            "SELECT id, referrer_user_id, status FROM referrals WHERE referred_user_id=?",
            (referred_user_id,)
        ).fetchone()
        if not row or row["status"] != "paid":
            return None
        referrer_user_id = int(row["referrer_user_id"])
        self.conn.execute("INSERT INTO reward_ledger (user_id, days, reason, created_at) VALUES (?,?,?,?)",
                          (referrer_user_id, days, f"referral:{referred_user_id}", self.now_iso()))
        self.conn.execute("UPDATE referrals SET status='rewarded' WHERE id=?", (int(row["id"]),))
        now = datetime.utcnow()
        u = self.conn.execute("SELECT paid_until FROM users WHERE id=?", (referrer_user_id,)).fetchone()
        if u and u["paid_until"]:
            pu = datetime.fromisoformat(u["paid_until"])
            base = pu if pu > now else now
        else:
            base = now
        new_pu = (base + timedelta(days=days)).replace(microsecond=0).isoformat()
        self.conn.execute("UPDATE users SET paid_until=?, status='active' WHERE id=?", (new_pu, referrer_user_id))
        self.conn.commit()
        return referrer_user_id
