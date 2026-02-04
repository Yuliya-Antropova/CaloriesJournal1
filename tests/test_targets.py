from bot.services.targets import compute_targets

def test_targets_sane():
    kcal, prot, fib = compute_targets("f", 32, 165, 65, "moderate", "lose")
    assert 1200 < kcal < 2600
    assert 80 < prot < 180
    assert fib in (25,30)
