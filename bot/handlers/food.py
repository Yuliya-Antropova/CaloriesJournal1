from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from datetime import datetime
from bot.services.analyzer import analyze, to_json, from_json, apply_refinement, AnalysisResult
from bot.services.access import is_active, ensure_status
from bot.keyboards import refine_keyboard
from bot.texts import HOW_TO

router = Router()

def _daily_tip_once(db, user_id: int, key: str) -> bool:
    today = datetime.utcnow().date().isoformat()
    prev = db.get_meta(user_id, key)
    if prev == today:
        return False
    db.set_meta(user_id, key, today)
    return True

@router.message(F.photo)
async def photo_entry(message: Message, db):
    user = ensure_status(db, db.get_or_create_user(message.from_user.id, message.chat.id, default_status=message.from_user.default_status))
    if not is_active(user):
        await message.answer("Доступ ограничен: триал закончился. Чтобы продолжить — /buy")
        return

    profile = db.get_profile(message.from_user.id_db)
    if not profile:
        await message.answer("Сначала заполни анкету: /start")
        return

    caption = message.caption or ""
    if len(caption.strip()) < 3:
        await message.answer("Добавь короткий комментарий к фото (1 фраза).\n" + HOW_TO)
        return

    ar = analyze(caption, has_photo=True)
    ts = datetime.utcnow().replace(microsecond=0).isoformat()
    photo_file_id = message.photo[-1].file_id
    entry_id = db.add_food_entry(
        user_id=message.from_user.id_db,
        ts_iso=ts,
        text=caption,
        photo_file_id=photo_file_id,
        parsed_json=to_json(ar),
        kcal_low=ar.kcal_low, kcal_high=ar.kcal_high, kcal_mid=ar.kcal_mid,
        conf=ar.conf, err_low=ar.err_low, err_high=ar.err_high
    )

    targets = db.get_targets(message.from_user.id_db)
    low, mid, high = db.today_kcal_sum(message.from_user.id_db, datetime.utcnow())
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

    if (not ar.has_reference) and _daily_tip_once(db, message.from_user.id_db, "tip_reference"):
        resp += "\nСовет: для меньшей погрешности делай фото строго сверху и клади банковскую карту в кадр."

    if ar.needs_refine:
        await message.answer(resp + "\nУточни одним тапом:", reply_markup=refine_keyboard(ar.refine_kind or "sauce", entry_id))
    else:
        await message.answer(resp)

@router.message(F.text)
async def text_entry(message: Message, db):
    if message.text and message.text.startswith("/"):
        return
    user = ensure_status(db, db.get_or_create_user(message.from_user.id, message.chat.id, default_status=message.from_user.default_status))
    if not is_active(user):
        await message.answer("Доступ ограничен: триал закончился. Чтобы продолжить — /buy")
        return
    profile = db.get_profile(message.from_user.id_db)
    if not profile:
        await message.answer("Сначала заполни анкету: /start")
        return

    text = (message.text or "").strip()
    if len(text) < 3:
        return
    ar = analyze(text, has_photo=False)
    ts = datetime.utcnow().replace(microsecond=0).isoformat()
    db.add_food_entry(
        user_id=message.from_user.id_db,
        ts_iso=ts,
        text=text,
        photo_file_id=None,
        parsed_json=to_json(ar),
        kcal_low=ar.kcal_low, kcal_high=ar.kcal_high, kcal_mid=ar.kcal_mid,
        conf=ar.conf, err_low=ar.err_low, err_high=ar.err_high
    )
    targets = db.get_targets(message.from_user.id_db)
    low, mid, high = db.today_kcal_sum(message.from_user.id_db, datetime.utcnow())
    remaining_mid = max(0, targets["kcal_target"] - mid)
    err_pct_high = int(round(ar.err_high * 100))
    await message.answer(
        f"Ок. ~{ar.kcal_mid} ккал (диапазон {ar.kcal_low}–{ar.kcal_high}), погрешность до ±{err_pct_high}%.\n"
        f"Осталось на день: ~{remaining_mid} ккал."
    )

@router.callback_query(F.data.startswith("refine:"))
async def refine(cb: CallbackQuery, db):
    # refine:<kind>:<val>:<entry_id>
    parts = cb.data.split(":")
    if len(parts) != 4:
        await cb.answer("Ошибка формата")
        return
    kind, val, entry_id_s = parts[1], parts[2], parts[3]
    try:
        entry_id = int(entry_id_s)
    except ValueError:
        await cb.answer("Ошибка")
        return

    entry = db.get_food_entry(entry_id, cb.from_user.id_db)
    if not entry:
        await cb.answer("Запись не найдена")
        return

    meta = from_json(entry["parsed_json"])
    comps = meta.get("components", ["блюдо"])
    ar0 = AnalysisResult(
        components=comps,
        kcal_low=entry["kcal_low"],
        kcal_high=entry["kcal_high"],
        kcal_mid=entry["kcal_mid"],
        conf=entry["conf"],
        err_low=entry["err_low"],
        err_high=entry["err_high"],
        note=meta.get("note", ""),
        needs_refine=False,
        refine_kind=None,
        has_reference=bool(meta.get("has_reference", False)),
    )

    ar1 = apply_refinement(ar0, kind, val)
    db.update_food_entry(entry_id, cb.from_user.id_db, to_json(ar1),
                         ar1.kcal_low, ar1.kcal_high, ar1.kcal_mid, ar1.conf, ar1.err_low, ar1.err_high)

    targets = db.get_targets(cb.from_user.id_db)
    low, mid, high = db.today_kcal_sum(cb.from_user.id_db, datetime.utcnow())
    remaining_mid = max(0, targets["kcal_target"] - mid)
    err_pct_high = int(round(ar1.err_high * 100))

    await cb.message.answer(
        f"Пересчитал: ~{ar1.kcal_mid} ккал (диапазон {ar1.kcal_low}–{ar1.kcal_high}), погрешность до ±{err_pct_high}%.\n"
        f"Осталось на день: ~{remaining_mid} ккал."
    )
    await cb.answer("Ок")
