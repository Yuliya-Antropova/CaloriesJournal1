from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery

from bot.keyboards import activity_keyboard, goal_keyboard
from bot.services.access import ensure_status

router = Router()


class Onb(StatesGroup):
    sex = State()
    age = State()
    height = State()
    weight = State()
    activity = State()
    goal = State()
    palm_len = State()
    palm_w = State()


def _calc_targets(sex: str, age: int, height_cm: float, weight_kg: float, activity: str, goal: str):
    """
    Упрощённая формула Mifflin–St Jeor + множители активности.
    Это MVP: достаточно стабильно для старта.
    """
    if sex == "m":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    af = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "high": 1.725,
        "athlete": 1.9,
    }.get(activity, 1.375)

    tdee = bmr * af

    if goal == "lose":
        kcal = int(round(tdee - 400))
    elif goal == "gain":
        kcal = int(round(tdee + 300))
    else:
        kcal = int(round(tdee))

    kcal = max(1200, kcal)  # нижняя страховка для MVP

    # очень грубо, но полезно как ориентир
    protein_g = int(round(weight_kg * (1.6 if goal == "lose" else 1.4)))
    fiber_g = 25 if sex == "f" else 30
    return kcal, protein_g, fiber_g


@router.message(Command("start"))
async def start_cmd(message: Message, db, user_row, state: FSMContext):
    ensure_status(db, user_row)
    await state.clear()
    await state.set_state(Onb.sex)
    await message.answer("Анкета. Пол? Ответь одной буквой: f / m")


@router.message(Onb.sex)
async def sex_step(message: Message, state: FSMContext):
    s = (message.text or "").strip().lower()
    if s not in ("f", "m"):
        await message.answer("Напиши f или m")
        return
    await state.update_data(sex=s)
    await state.set_state(Onb.age)
    await message.answer("Возраст (числом)? Например: 32")


@router.message(Onb.age)
async def age_step(message: Message, state: FSMContext):
    try:
        age = int((message.text or "").strip())
        if age < 10 or age > 90:
            raise ValueError
    except Exception:
        await message.answer("Возраст числом, например 32")
        return
    await state.update_data(age=age)
    await state.set_state(Onb.height)
    await message.answer("Рост в см? Например: 165")


@router.message(Onb.height)
async def height_step(message: Message, state: FSMContext):
    try:
        h = float((message.text or "").strip().replace(",", "."))
        if h < 120 or h > 220:
            raise ValueError
    except Exception:
        await message.answer("Рост в см, например 165")
        return
    await state.update_data(height_cm=h)
    await state.set_state(Onb.weight)
    await message.answer("Вес в кг? Например: 62.5")


@router.message(Onb.weight)
async def weight_step(message: Message, state: FSMContext):
    try:
        w = float((message.text or "").strip().replace(",", "."))
        if w < 30 or w > 200:
            raise ValueError
    except Exception:
        await message.answer("Вес в кг, например 62.5")
        return
    await state.update_data(weight_kg=w)
    await state.set_state(Onb.activity)
    await message.answer("Активность:", reply_markup=activity_keyboard())


@router.callback_query(Onb.activity, F.data.startswith("act:"))
async def activity_cb(cb: CallbackQuery, state: FSMContext):
    activity = cb.data.split(":", 1)[1]
    await state.update_data(activity=activity)
    await state.set_state(Onb.goal)
    await cb.message.answer("Цель:", reply_markup=goal_keyboard())
    await cb.answer()


@router.callback_query(Onb.goal, F.data.startswith("goal:"))
async def goal_cb(cb: CallbackQuery, db, user_row, state: FSMContext):
    goal = cb.data.split(":", 1)[1]
    await state.update_data(goal=goal)

    data = await state.get_data()
    sex = data["sex"]
    age = int(data["age"])
    height_cm = float(data["height_cm"])
    weight_kg = float(data["weight_kg"])
    activity = data["activity"]

    user = ensure_status(db, user_row)

    db.upsert_profile(
        user_id=user.id,
        sex=sex,
        age=age,
        height_cm=height_cm,
        weight_kg=weight_kg,
        activity=activity,
        goal=goal,
        palm_len_cm=None,
        palm_w_cm=None,
    )

    kcal, protein_g, fiber_g = _calc_targets(sex, age, height_cm, weight_kg, activity, goal)
    db.upsert_targets(user.id, kcal_target=kcal, protein_g=protein_g, fiber_g=fiber_g)

    await cb.message.answer(
        f"Готово.\n"
        f"Цель на день: {kcal} ккал\n"
        f"Белок: ~{protein_g} г, клетчатка: ~{fiber_g} г\n\n"
        "Теперь отправь фото еды с подписью (1 фраза)."
    )
    await state.clear()
    await cb.answer()
