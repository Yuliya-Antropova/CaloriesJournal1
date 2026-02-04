from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from bot.services.analyzer import analyze, to_json, from_json, apply_refinement
from bot.services.access import is_active, ensure_status
from bot.keyboards import refine_keyboard

router = Router()


def _daily_tip_once(db, user_id: int, key: str) -> bool:
    today = datetime.utcnow().date().isoformat()
    prev = db.get_meta(user_id, key)
    if prev == today:
        return False
    db.set_meta(user_id, key, today)
    return True


@router.message(F.photo)
async def photo_entry(message: Message, db, user_row):
    user = ensure_status(db, user_row)
    if not is_active(user):
        await message.answer("Доступ ограничен: триал закончился. Чтобы продолжить — /buy")
        return

    profile = db.get_profile(user.id)
    if not profile:
        await message.answer("Сначала заполни анкету: /start")
        return

    caption = (message.caption or "").strip()
    if len(caption) < 3:
        await message.answer("Добавь короткий комментарий к фото (1 фраза).")
        return

    ar = analyze(caption, has_photo=True)
    ts = datetime.utcnow().replace(microsecond=0).isoformat()
    photo_file_id = message.photo[-1].file_id

    entry_id = db.add_food_entry(
        user_id=user.id,
        ts_iso=ts,
        text=caption,
        photo_file_id=photo_file_id,
        parsed_json=to_json(ar),
        kcal_low=ar.kcal_low,
        kcal_high=ar.kcal_high,
        kcal_mid=ar.kcal_mid,
        conf=ar.conf,
        err_low=ar.err_low,
        err_high=ar.err_high,
    )

    targets = db.get_targets(user.id)
    low, mid, high = db.today_kcal_sum(user.id, datetime.utcnow())
    remaining_low = max(0, targets["kcal_target"] - high)
    remaining_mid = max(0, targets["kcal_target"] - mid)

    components = ", ".join(ar.components[:6])
    err_pct_low = int(round(ar.err_low * 100))
    err_pct_high = int(round(ar.err_high * 100))

    resp = (
        f"Понял так: {components}\n"
        f"Калории: ~{ar.kcal_mid} ккал (диапазон {ar.kcal_low}–{ar.kcal_high})\n"
        f"Погрешность: ±{err_pct_low}–{err_pct_high}%\n\n"
        f"За сегодня: ~{mid} ккал\n"
        f"Осталось: ~{remaining_mid} ккал (консервативно ≥{remaining_low})\n"
    )

    if (not ar.has_reference) and _daily_tip_once(db, user.id, "tip_reference"):
        resp += (
            "\nСовет: для меньшей погрешности делай фото строго сверху "
            "и клади банковскую карту в кадр."
        )

    if ar.needs_refine:
        await message.answer(
            resp + "\n\nУточни одним тапом:",
            reply_markup=refine_keyboard(ar.refine_kind or "sauce", entry_id),
        )
    else:
        await message.answer(resp)


@router.message(F.text)
async def text_entry(message: Message, db, user_row):
    # не перехватываем команды
    if message.text and message.text.startswith("/"):
        return

    user = ensure_status(db, user_row)
    if not is_active(user):
        await message.answer("Доступ ограничен: триал закончился. Чтобы продолжить — /buy")
        return

    profile = db.get_profile(user.id)
    if not profile:
        await message.answer("Сначала заполни анкету: /start")
        return

    text = (message.text or "").strip()
    if len(text) < 3:
        return

    ar = analyze(text, has_photo=False)
    ts = datetime.utcnow().replace(microsecond=0).isoformat()

    db.add_food_entry(
        user_id=user.id,
        ts_iso=ts,
        text=text,
        photo_file_id=None,
        parsed_json=to_json(ar),
        kcal_low=ar.kcal_low,
        kcal_high=ar.kcal_high,
        kcal_mid=ar.kcal_mid,
        conf=ar.conf,
        err_low=ar.err_low,
        err_high=ar.err_high,
    )

    targets = db.get_targets(user.id)
    low, mid, high = db.today_kcal_sum(user.id, datetime.utcnow())
    remaining_mid = max(0, targets["kcal_target"] - mid)
    err_pct_high = int(round(ar.err_high * 100))

    await message.answer(
        f"Ок. ~{ar.kcal_mid} ккал (диапазон {ar.kcal_low}–{ar.kcal_high}), "
        f"погрешность до ±{err_pct_high}%.\n"
        f"Осталось на день: ~{remaining_mid} ккал."
    )


@router.callback_query(F.data.startswith("refine:"))
async def refine(cb: CallbackQuery, db, user_row):
    # refine:<kind>:<val>:<entry_id>
    parts = (cb.data or "").split(":")
    if len(parts) != 4:
        await cb.answer("Ошибка формата")
        return

    kind, val, entry_id_s = parts[1], parts[2], parts[3]
    try:
        entry_id = int(entry_id_s)
    except ValueError:
        await cb.answer("Ошибка")
        return

    user = ensure_status(db, user_row)
    entry = db.get_food_entry(entry_id, user.id)
    if not entry:
        await cb.answer("Запись не найдена")
        return

    ar = from_json(entry["parsed_json"])
    ar2 = apply_refinement(ar, kind, val)

    db.update_food_entry(
        entry_id=entry_id,
        user_id=user.id,
        parsed_json=to_json(ar2),
        kcal_low=ar2.kcal_low,
        kcal_high=ar2.kcal_high,
        kcal_mid=ar2.kcal_mid,
        conf=ar2.conf,
        err_low=ar2.err_low,
        err_high=ar2.err_high,
    )

    targets = db.get_targets(user.id)
    low, mid, high = db.today_kcal_sum(user.id, datetime.utcnow())
    remaining_low = max(0, targets["kcal_target"] - high)
    remaining_mid = max(0, targets["kcal_target"] - mid)

    await cb.message.answer(
        "Пересчитал.\n"
        f"Калории: ~{ar2.kcal_mid} ккал (диапазон {ar2.kcal_low}–{ar2.kcal_high})\n"
        f"За сегодня: ~{mid} ккал\n"
        f"Осталось: ~{remaining_mid} ккал (консервативно ≥{remaining_low})"
    )
    await cb.answer("Ок")
