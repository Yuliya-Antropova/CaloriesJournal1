from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.access import ensure_status, is_active

router = Router()


@router.message(Command("help"))
async def help_cmd(message: Message, db, user_row):
    ensure_status(db, user_row)
    await message.answer(
        "Как пользоваться:\n"
        "1) Фото еды + 1 фраза комментария (что это и примерно сколько/как приготовлено)\n"
        "2) Лучше фото сверху, без сильных теней.\n"
        "3) Если есть возможность — положи в кадр банковскую карту (референс размера).\n\n"
        "Команды:\n"
        "/today — итоги дня\n"
        "/beta — статус доступа\n"
        "/invite — промокод для рекомендаций\n"
        "/promo <CODE> — применить промокод\n"
        "/buy — оплата (если подключена)"
    )


@router.message(Command("today"))
async def today_cmd(message: Message, db, user_row):
    user = ensure_status(db, user_row)

    targets = db.get_targets(user.id)
    if not targets:
        await message.answer("Сначала заполни анкету: /start")
        return

    low, mid, high = db.today_kcal_sum(user.id, __import__("datetime").datetime.utcnow())
    remaining_mid = max(0, targets["kcal_target"] - mid)
    remaining_low = max(0, targets["kcal_target"] - high)

    await message.answer(
        f"За сегодня: ~{mid} ккал (диапазон {low}–{high})\n"
        f"Цель: {targets['kcal_target']} ккал\n"
        f"Осталось: ~{remaining_mid} ккал (консервативно ≥{remaining_low})"
    )


@router.message(Command("beta"))
async def beta_cmd(message: Message, db, user_row):
    u = ensure_status(db, user_row)
    status = u.status
    trial_end = u.trial_end or "—"
    paid_until = u.paid_until or "—"

    extra = ""
    if not is_active(u):
        extra = "\n\nДоступ ограничен. Для оплаты: /buy"

    await message.answer(
        f"Статус: {status}\n"
        f"Триал до: {trial_end}\n"
        f"Оплачено до: {paid_until}"
        f"{extra}"
    )


@router.message(Command("invite"))
async def invite_cmd(message: Message, db, user_row):
    u = ensure_status(db, user_row)
    code = db.get_or_create_promo_code(u.id)
    await message.answer(
        f"Твой промокод: <code>{code}</code>\n\n"
        "Условия:\n"
        "— Новому пользователю: -50% на 1 месяц (при первой оплате)\n"
        "— Тебе: +7 дней после первой оплаты приглашённого"
    )


@router.message(Command("promo"))
async def promo_cmd(message: Message, db, user_row):
    u = ensure_status(db, user_row)
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /promo NIGMA-XXXXXX")
        return

    code = parts[1].strip().upper()
    ok, msg, _referrer = db.apply_promo_for_new_user(u.id, code)
    await message.answer(msg)
