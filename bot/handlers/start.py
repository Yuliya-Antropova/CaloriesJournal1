from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.states import Onboarding
from bot.texts import START_INTRO, DISCLAIMER
from bot.keyboards import activity_keyboard, goal_keyboard
from bot.services.targets import compute_targets

router = Router()

@router.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(START_INTRO + "\n\nУкажи пол: напиши 'ж' или 'м'.\n" + DISCLAIMER)
    await state.set_state(Onboarding.sex)

@router.message(Onboarding.sex)
async def sex(message: Message, state: FSMContext):
    t = (message.text or "").strip().lower()
    if t in ("ж","жен","женщина","f","female"):
        await state.update_data(sex="f")
    elif t in ("м","муж","мужчина","m","male"):
        await state.update_data(sex="m")
    else:
        await message.answer("Напиши только: 'ж' или 'м'.")
        return
    await message.answer("Возраст (полных лет):")
    await state.set_state(Onboarding.age)

@router.message(Onboarding.age)
async def age(message: Message, state: FSMContext):
    try:
        age = int((message.text or "").strip())
        if not (12 <= age <= 90):
            raise ValueError
    except ValueError:
        await message.answer("Возраст числом (12–90).")
        return
    await state.update_data(age=age)
    await message.answer("Рост (см):")
    await state.set_state(Onboarding.height)

@router.message(Onboarding.height)
async def height(message: Message, state: FSMContext):
    try:
        h = float((message.text or "").replace(",", ".").strip())
        if not (120 <= h <= 220):
            raise ValueError
    except ValueError:
        await message.answer("Рост в см (120–220).")
        return
    await state.update_data(height_cm=h)
    await message.answer("Вес (кг):")
    await state.set_state(Onboarding.weight)

@router.message(Onboarding.weight)
async def weight(message: Message, state: FSMContext, db):
    try:
        w = float((message.text or "").replace(",", ".").strip())
        if not (35 <= w <= 220):
            raise ValueError
    except ValueError:
        await message.answer("Вес в кг (35–220).")
        return
    await state.update_data(weight_kg=w)
    await message.answer("Активность:", reply_markup=activity_keyboard())
    await state.set_state(Onboarding.activity)

@router.callback_query(Onboarding.activity, F.data.startswith("act:"))
async def activity(cb: CallbackQuery, state: FSMContext):
    act = cb.data.split(":",1)[1]
    await state.update_data(activity=act)
    await cb.message.answer("Цель:", reply_markup=goal_keyboard())
    await cb.answer()
    await state.set_state(Onboarding.goal)

@router.callback_query(Onboarding.goal, F.data.startswith("goal:"))
async def goal(cb: CallbackQuery, state: FSMContext, db):
    goal = cb.data.split(":",1)[1]
    await state.update_data(goal=goal)
    data = await state.get_data()

    # persist
    prof = {
        "sex": data["sex"],
        "age": data["age"],
        "height_cm": data["height_cm"],
        "weight_kg": data["weight_kg"],
        "activity": data["activity"],
        "goal": data["goal"],
        "palm_len_cm": None,
        "palm_w_cm": None,
    }
    db.upsert_profile(cb.from_user.id_db, **prof)  # id_db injected in middleware
    kcal, prot, fib = compute_targets(prof["sex"], prof["age"], prof["height_cm"], prof["weight_kg"], prof["activity"], prof["goal"])
    db.upsert_targets(cb.from_user.id_db, kcal, prot, fib)

    await cb.message.answer(
        f"Готово. Дневная цель: {kcal} ккал.\n"
        f"Ориентир: белок {prot} г/день, клетчатка {fib} г/день.\n\n"
        "Теперь просто отправляй фото еды с комментарием.\n"
        "Пример: «индейка в сливочном, картошка, соуса мало»"
    )
    await cb.answer()
    await state.clear()
