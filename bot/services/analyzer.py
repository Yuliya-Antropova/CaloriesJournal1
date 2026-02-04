from __future__ import annotations
import re, json
from dataclasses import dataclass
from typing import Optional

@dataclass
class AnalysisResult:
    components: list[str]
    kcal_low: int
    kcal_high: int
    kcal_mid: int
    conf: float
    err_low: float
    err_high: float
    note: str
    needs_refine: bool
    refine_kind: Optional[str]  # 'sauce'|'oil'|'portion'|None
    has_reference: bool

BASE_KCAL = {
    "индейк": 220,
    "куриц": 240,
    "рыб": 220,
    "говя": 320,
    "свини": 360,
    "яйц": 180,
    "омлет": 250,
    "карто": 260,
    "рис": 240,
    "паста": 320,
    "макарон": 320,
    "салат": 180,
    "овощ": 120,
    "сыр": 180,
    "хлеб": 160,
    "кофе": 20,
    "молок": 80,
    "йогур": 150,
    "суп": 220,
    "десерт": 380,
    "пицц": 420,
    "бургер": 520,
    "шаур": 650,
}

HIGH_RISK = [
    ("сливоч", "sauce"),
    ("соус", "sauce"),
    ("майон", "sauce"),
    ("масл", "oil"),
    ("жарен", "oil"),
    ("сыр", "portion"),
    ("орех", "portion"),
]

PORTION_MOD = {
    "мало": 0.85,
    "чуть": 0.90,
    "немного": 0.90,
    "обычно": 1.0,
    "средне": 1.0,
    "норм": 1.0,
    "много": 1.20,
    "больш": 1.25,
}

def _tokenize_ru(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()

def _detect_reference(text: str) -> bool:
    t = _tokenize_ru(text)
    return ("карта" in t) or ("card" in t) or ("visa" in t) or ("mastercard" in t)

def analyze(text: str, has_photo: bool, has_reference: Optional[bool]=None) -> AnalysisResult:
    t = _tokenize_ru(text)
    comps = []
    score = 0
    for k, kcal in BASE_KCAL.items():
        if k in t:
            comps.append(k)
            score += kcal

    if not comps:
        score = 450
        comps = ["блюдо"]
        conf = 0.35
    else:
        conf = 0.55 + min(0.35, 0.08 * len(comps))

    portion_factor = 1.0
    for word, f in PORTION_MOD.items():
        if word in t:
            portion_factor = f
            break

    extra = 0
    needs_refine = False
    refine_kind = None
    for kw, kind in HIGH_RISK:
        if kw in t:
            needs_refine = True
            refine_kind = kind
            if kind == "sauce":
                extra += 120
            elif kind == "oil":
                extra += 100
            elif kind == "portion":
                extra += 80
            break

    base = int(round((score + extra) * portion_factor))

    if has_reference is None:
        has_reference = _detect_reference(text)

    # Error model
    err = 0.22 if has_photo else 0.28
    if has_reference:
        err -= 0.04
        conf += 0.05
    if needs_refine:
        err += 0.06
        conf -= 0.05

    conf = max(0.2, min(0.9, conf))
    err_low = max(0.08, min(0.55, err - 0.05))
    err_high = max(0.10, min(0.60, err + 0.07))

    kcal_low = int(round(base * (1 - err_high)))
    kcal_high = int(round(base * (1 + err_high)))
    kcal_mid = base

    note = "Оценка по описанию" + (" + фото" if has_photo else "") + (", с референсом" if has_reference else "")
    return AnalysisResult(
        components=comps,
        kcal_low=max(0, kcal_low),
        kcal_high=max(kcal_low+1, kcal_high),
        kcal_mid=max(0, kcal_mid),
        conf=conf,
        err_low=err_low,
        err_high=err_high,
        note=note,
        needs_refine=needs_refine,
        refine_kind=refine_kind,
        has_reference=bool(has_reference),
    )

def apply_refinement(ar: AnalysisResult, kind: str, val: str) -> AnalysisResult:
    # deterministic adjustments to shrink error and shift kcal
    kcal = ar.kcal_mid
    err = ar.err_high

    if kind == "sauce":
        if val == "low":
            kcal -= 60
        elif val == "mid":
            kcal += 0
        elif val == "high":
            kcal += 120
        err = max(0.12, err - 0.05)
    elif kind == "oil":
        if val == "none":
            kcal -= 80
        elif val == "little":
            kcal += 0
        elif val == "1tbsp":
            kcal += 90
        err = max(0.12, err - 0.05)
    elif kind == "portion":
        if val == "small":
            kcal = int(round(kcal * 0.85))
        elif val == "normal":
            kcal = kcal
        elif val == "large":
            kcal = int(round(kcal * 1.25))
        err = max(0.12, err - 0.04)

    kcal = max(0, kcal)
    kcal_low = int(round(kcal * (1 - err)))
    kcal_high = int(round(kcal * (1 + err)))

    return AnalysisResult(
        components=ar.components,
        kcal_low=max(0, kcal_low),
        kcal_high=max(kcal_low+1, kcal_high),
        kcal_mid=kcal,
        conf=min(0.95, ar.conf + 0.05),
        err_low=max(0.06, err - 0.04),
        err_high=err,
        note=ar.note + f" | уточнение:{kind}:{val}",
        needs_refine=False,
        refine_kind=None,
        has_reference=ar.has_reference,
    )

def to_json(ar: AnalysisResult) -> str:
    return json.dumps({
        "components": ar.components,
        "note": ar.note,
        "needs_refine": ar.needs_refine,
        "refine_kind": ar.refine_kind,
        "has_reference": ar.has_reference,
    }, ensure_ascii=False)

def from_json(s: str) -> dict:
    try:
        return json.loads(s)
    except Exception:
        return {}
