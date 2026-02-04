from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def refine_keyboard(kind: str, entry_id: int) -> InlineKeyboardMarkup:
    if kind == "sauce":
        buttons = [
            [InlineKeyboardButton(text="Соуса мало", callback_data=f"refine:sauce:low:{entry_id}"),
             InlineKeyboardButton(text="Средне", callback_data=f"refine:sauce:mid:{entry_id}"),
             InlineKeyboardButton(text="Много", callback_data=f"refine:sauce:high:{entry_id}")]
        ]
    elif kind == "oil":
        buttons = [
            [InlineKeyboardButton(text="Масла нет", callback_data=f"refine:oil:none:{entry_id}"),
             InlineKeyboardButton(text="Чуть-чуть", callback_data=f"refine:oil:little:{entry_id}"),
             InlineKeyboardButton(text="~1 ст.л", callback_data=f"refine:oil:1tbsp:{entry_id}")]
        ]
    else:  # portion
        buttons = [
            [InlineKeyboardButton(text="Порция маленькая", callback_data=f"refine:portion:small:{entry_id}"),
             InlineKeyboardButton(text="Обычная", callback_data=f"refine:portion:normal:{entry_id}"),
             InlineKeyboardButton(text="Большая", callback_data=f"refine:portion:large:{entry_id}")]
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def activity_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сидячая", callback_data="act:sedentary"),
         InlineKeyboardButton(text="Лёгкая", callback_data="act:light")],
        [InlineKeyboardButton(text="Средняя", callback_data="act:moderate"),
         InlineKeyboardButton(text="Высокая", callback_data="act:high")],
        [InlineKeyboardButton(text="Спорт/очень высокая", callback_data="act:athlete")]
    ])

def goal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Похудение", callback_data="goal:lose"),
         InlineKeyboardButton(text="Поддержание", callback_data="goal:maintain"),
         InlineKeyboardButton(text="Набор", callback_data="goal:gain")]
    ])
