from __future__ import annotations
from aiogram import Router, F
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from datetime import datetime, timedelta

router = Router()

@router.message(lambda m: m.text == "/buy")
async def buy(message: Message, db, cfg):
    # If provider token not set, just explain
    if not cfg.provider_token:
        await message.answer("Оплата не настроена (нет PROVIDER_TOKEN). Сейчас можно тестировать в beta whitelist.")
        return

    # Determine discount eligibility
    has_discount = db.get_discount_for_user(message.from_user.id_db) == 1
    price_rub = cfg.price_rub
    if has_discount:
        price_rub = int(round(price_rub * (100 - cfg.discount_percent) / 100))

    prices = [LabeledPrice(label="Подписка 1 месяц", amount=price_rub * 100)]  # in kopeks
    title = "Подписка Nigma Calorie Bot"
    descr = "Доступ на 30 дней. Оценка калорий без весов: фото + комментарий."
    payload = f"sub:{message.from_user.id_db}:{'disc' if has_discount else 'full'}"

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
async def successful_payment(message: Message, db):
    # Activate 30 days from now (or extend)
    now = datetime.utcnow()
    user_row = db.get_or_create_user(message.from_user.id, message.chat.id, default_status=message.from_user.default_status)

    base = now
    if user_row.paid_until:
        pu = datetime.fromisoformat(user_row.paid_until)
        if pu > now:
            base = pu
    paid_until = (base + timedelta(days=30)).replace(microsecond=0).isoformat()
    db.set_paid_until(message.from_user.id_db, paid_until)

    # If referral discount reserved -> mark paid and reward referrer
    db.mark_first_payment(message.from_user.id_db)
    referrer_id = db.reward_referrer_if_paid(message.from_user.id_db, days=7)
    if referrer_id:
        # notify referrer (if chat_id known)
        ref_user = db.conn.execute("SELECT chat_id FROM users WHERE id=?", (referrer_id,)).fetchone()
        if ref_user and ref_user["chat_id"]:
            try:
                await message.bot.send_message(ref_user["chat_id"], "По твоей рекомендации прошла оплата — начислил +7 дней доступа.")
            except Exception:
                pass

    await message.answer("Оплата прошла. Подписка активна на 30 дней ✅")
