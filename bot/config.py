import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    bot_token: str
    db_path: str
    tz: str
    beta_whitelist: set[int]
    provider_token: str | None
    price_rub: int
    discount_percent: int

def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required")
    db_path = os.getenv("DB_PATH", "bot.db").strip()
    tz = os.getenv("TZ", "Asia/Yerevan").strip()
    wl_raw = os.getenv("BETA_WHITELIST", "").strip()
    wl = set()
    if wl_raw:
        for x in wl_raw.split(","):
            x = x.strip()
            if x:
                try:
                    wl.add(int(x))
                except ValueError:
                    pass

    provider_token = os.getenv("PROVIDER_TOKEN", "").strip() or None
    price_rub = int(os.getenv("PRICE_RUB", "300").strip())
    discount_percent = int(os.getenv("REF_DISCOUNT_PERCENT", "50").strip())
    return Config(
        bot_token=token,
        db_path=db_path,
        tz=tz,
        beta_whitelist=wl,
        provider_token=provider_token,
        price_rub=price_rub,
        discount_percent=discount_percent,
    )
