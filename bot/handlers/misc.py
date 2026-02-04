from aiogram import Router
from aiogram.types import Message
from datetime import datetime
from bot.texts import HOW_TO

router = Router()

@router.message(lambda m: m.text == "/today")
async def today(message: Message, db):
    prof = db.get_profile(message.from_user.id_db)
    if not prof:
        await message.answer("Сначала /start")
        return
    targets = db.get_targets(message.from_user.id_db)
    low, mid, high = db.today_kcal_sum(message.from_user.id_db, datetime.utcnow())
    rem = max(0, targets["kcal_target"] - mid)
    await message.answer(
        f"Сегодня: ~{mid} ккал (диапазон {low}–{high})\n"
        f"Цель: {targets['kcal_target']} ккал\n"
        f"Осталось: ~{rem} ккал."
    )

@router.message(lambda m: m.text == "/help")
async def help_(message: Message):
    await message.answer(HOW_TO)

@router.message(lambda m: m.text == "/invite")
async def invite(message: Message, db):
    code = db.get_or_create_promo_code(message.from_user.id_db)
    await message.answer(
        f"Твой промокод: {code}\n\n"
        "Друг: -50% на 1-й месяц после триала.\n"
        "Ты: +7 дней бесплатно после его первой оплаты.\n\n"
        "Команда для друга: /promo " + code
    )

@router.message(lambda m: m.text and m.text.startswith("/promo"))
async def promo(message: Message, db):
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: /promo NIGMA-XXXXXX")
        return
    code = parts[1].strip().upper()
    ok, msg, _ = db.apply_promo_for_new_user(message.from_user.id_db, code)
    await message.answer(msg if ok else ("Ошибка: " + msg))

@router.message(lambda m: m.text == "/beta")
async def beta(message: Message, db):
    u = db.get_or_create_user(message.from_user.id, message.chat.id, default_status=message.from_user.default_status)
    await message.answer(f"Статус: {u.status}\nТриал до: {u.trial_end}\nОплачено до: {u.paid_until}\n\nДля оплаты: /buy")
