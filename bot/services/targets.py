from __future__ import annotations
import math

ACTIVITY_FACTOR = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "high": 1.725,
    "athlete": 1.9,
}

def mifflin_st_jeor(sex: str, age: int, height_cm: float, weight_kg: float) -> float:
    # BMR
    s = 5 if sex == "m" else -161
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + s

def compute_targets(sex: str, age: int, height_cm: float, weight_kg: float, activity: str, goal: str) -> tuple[int,int,int]:
    bmr = mifflin_st_jeor(sex, age, height_cm, weight_kg)
    tdee = bmr * ACTIVITY_FACTOR.get(activity, 1.375)

    if goal == "lose":
        kcal = tdee * 0.85  # ~15% deficit
    elif goal == "gain":
        kcal = tdee * 1.10  # mild surplus
    else:
        kcal = tdee

    kcal_target = int(round(kcal))

    # Simple evidence-aligned heuristics (not medical):
    # protein: higher if losing, moderate otherwise
    if goal == "lose":
        protein = 1.8 * weight_kg
    elif goal == "gain":
        protein = 1.6 * weight_kg
    else:
        protein = 1.4 * weight_kg

    protein_g = int(round(protein))
    fiber_g = 25 if sex == "f" else 30
    return kcal_target, protein_g, fiber_g
