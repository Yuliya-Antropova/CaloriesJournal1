# Nigma Calorie Bot (MVP, no-scales)

Telegram bot MVP: photo + short comment -> estimated calories (range) + remaining daily budget.
Includes:
- Onboarding questionnaire (sex/age/height/weight/activity/goal)
- Trial/subscription state machine
- Telegram Payments (one-month purchase) if `PROVIDER_TOKEN` is set
- Referral promo codes: new user gets discount on first paid month, referrer gets +7 days after first payment
- SQLite storage

## Requirements
- Python 3.11+
- Telegram bot token from @BotFather
- (Optional) Payment provider token for Telegram Payments

## Quick start
```bash
cd nigma_calorie_bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export BOT_TOKEN="123:ABC"
export TZ="Asia/Yerevan"
# optional beta whitelist (free access)
export BETA_WHITELIST="12345678,87654321"

# optional payments
export PROVIDER_TOKEN="381764678:TEST:..."
export PRICE_RUB="300"
export REF_DISCOUNT_PERCENT="50"

python -m bot.main
```

## Commands
- /start — onboarding
- /today — today's summary
- /help — photo protocol
- /invite — your promo code
- /promo CODE — apply promo code (new users)
- /buy — buy 1 month subscription (if payments enabled)
- /beta — status

## Photo logging
Send a photo with a caption like:
`Индейка в сливочном соусе, картошка, соуса мало`
Bot responds with kcal range + remaining; if high-risk (sauce/oil/portion) it shows one-tap refinement buttons.
Refinement **recalculates** the logged entry and updates daily totals.

## Tests
```bash
pytest -q
```
