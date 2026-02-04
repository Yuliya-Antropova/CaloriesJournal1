from bot.services.analyzer import analyze, apply_refinement

def test_analyze_caption():
    ar = analyze("Индейка в сливочном соусе с картошкой, соуса мало", has_photo=True, has_reference=True)
    assert ar.kcal_low < ar.kcal_mid < ar.kcal_high
    assert ar.needs_refine is True
    ar2 = apply_refinement(ar, "sauce", "low")
    assert ar2.err_high <= ar.err_high

def test_analyze_fallback():
    ar = analyze("что-то непонятное", has_photo=False, has_reference=False)
    assert ar.kcal_mid > 0
