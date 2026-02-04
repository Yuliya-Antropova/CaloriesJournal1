from __future__ import annotations
from aiogram import Router, F
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from datetime import datetime, timedelta
from bot.services.access import ensure_status

router = Router()

@router.message(lambda m: m.text == "/buy")
async def buy(message: Message, db, cfg, user_row):
    user = ensure_status(db, user_row)
    # If provider token not set, just explain
    if not cfg.provider_token:
        await message.answer("Оплата не настроена (нет PROVIDER_TOKEN). Сейчас можно тестировать в beta whitelist.")
        return

    # Determine discount eligibility
    has_discount = db.get_discount_for_user(user.id) == 1
    price_rub = cfg.price_rub
    if has_discount:
        price_rub = int(round(price_rub * (100 - cfg.discount_percent) / 100))

    prices = [LabeledPrice(label="Подписка 1 месяц", amount=price_rub * 100)]  # in kopeks
    title = "Подписка Nigma Calorie Bot"
    descr = "Доступ на 30 дней. Оценка калорий без весов: фото + комментарий."
    payload = f"sub:{user.id}:{'disc' if has_discount else 'full'}"

    await message.bot.send_invoice(
        chat_id=message.chat.id,
        title=title,
        description=descr,
        payload=payload,
        provider_token=cfg.provider_token,
        currency="RUB",
        prices=prices,
        start_parameter="nigma_sub",
    )

@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message: Message, db, user_row):
    user = ensure_status(db, user_row)
    # Activate 30 days from now (or extend)
    now = datetime.utcnow()
    user_row = ensure_status(db, user_row)
base = now
    if user_row.paid_until:
        pu = datetime.fromisoformat(user_row.paid_until)
        if pu > now:
            base = pu
    paid_until = (base + timedelta(days=30)).replace(microsecond=0).isoformat()
    db.set_paid_until(user.id, paid_until)

    # If referral discount reserved -> mark paid and reward referrer
    db.mark_first_payment(user.id)
    referrer_id = db.reward_referrer_if_paid(user.id, days=7)
    if referrer_id:
        # notify referrer (if chat_id known)
        ref_user = db.conn.execute("SELECT chat_id FROM users WHERE id=?", (referrer_id,)).fetchone()
        if ref_user and ref_user["chat_id"]:
            try:
                await message.bot.send_message(ref_user["chat_id"], "По твоей рекомендации прошла оплата — начислил +7 дней доступа.")
            except Exception:
                pass

    await message.answer("Оплата прошла. Подписка активна на 30 дней ✅")