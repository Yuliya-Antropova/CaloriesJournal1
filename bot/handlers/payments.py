from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery

from bot.services.access import ensure_status

router = Router()


def _parse_paid_until(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


@router.message(Command("buy"))
async def buy_cmd(message: Message, db, user_row, bot, cfg):
    u = ensure_status(db, user_row)

    if not cfg.provider_token:
        await message.answer("Оплата пока не подключена. Тестовый доступ активен.")
        return

    base_price_rub = int(cfg.price_rub)
    discount_flag = db.get_discount_for_user(u.id)  # 1 если скидка зарезервирована
    discount_percent = int(cfg.ref_discount_percent) if discount_flag else 0

    final_rub = base_price_rub
    if discount_percent > 0:
        final_rub = max(1, int(round(base_price_rub * (100 - discount_percent) / 100)))

    prices = [LabeledPrice(label="Доступ на 30 дней", amount=final_rub * 100)]  # копейки
    title = "Подписка на 30 дней"
    description = "Доступ к подсчёту калорий в боте на 30 дней."
    payload = f"sub_30d:{u.id}:{final_rub}"

    await bot.send_invoice(
        chat_id=message.chat.id,
        title=title,
        description=description,
        payload=payload,
        provider_token=cfg.provider_token,
        currency="RUB",
        prices=prices,
        start_parameter="buy",
    )


@router.pre_checkout_query()
async def pre_checkout(preq: PreCheckoutQuery, bot):
    await bot.answer_pre_checkout_query(preq.id, ok=True)


@router.message(lambda m: m.successful_payment is not None)
async def successful_payment(message: Message, db, user_row, bot):
    u = ensure_status(db, user_row)

    now = datetime.utcnow()
    current_paid = _parse_paid_until(u.paid_until)

    # если уже оплачено и срок в будущем — продлеваем оттуда, иначе от сейчас
    base = current_paid if (current_paid and current_paid > now) else now
    new_paid_until = (base + timedelta(days=30)).replace(microsecond=0).isoformat()

    db.set_paid_until(u.id, new_paid_until)

    # если пользователь пришёл по рефералке — отмечаем первую оплату и начисляем рефереру +7 дней
    db.mark_first_payment(u.id)
    referrer_user_id = db.reward_referrer_if_paid(u.id, days=7)
    if referrer_user_id:
        # пробуем уведомить реферера (если известен chat_id)
        ref_row = db.conn.execute("SELECT chat_id FROM users WHERE id=?", (referrer_user_id,)).fetchone()
        if ref_row and ref_row["chat_id"]:
            try:
                await bot.send_message(
                    chat_id=int(ref_row["chat_id"]),
                    text="Твой друг оплатил подписку 🎉 Начислил тебе +7 дней бесплатно.",
                )
            except Exception:
                pass

    await message.answer(f"Оплата прошла. Доступ активен до: {new_paid_until}")
