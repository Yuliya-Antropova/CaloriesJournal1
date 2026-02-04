from aiogram.fsm.state import StatesGroup, State

class Onboarding(StatesGroup):
    sex = State()
    age = State()
    height = State()
    weight = State()
    activity = State()
    goal = State()
    palm_len = State()
    palm_w = State()
