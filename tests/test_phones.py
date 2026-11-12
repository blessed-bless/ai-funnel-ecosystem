from aifunnel.domain.phones import normalize_phone


def test_normalize_phone_variants():
    assert normalize_phone("+7 (900) 111-22-33") == "79001112233"
    assert normalize_phone("8 900 111 22 33") == "79001112233"
    assert normalize_phone("9001112233") == "79001112233"
    assert normalize_phone("") is None
    assert normalize_phone(None) is None
    assert normalize_phone("abc") is None


def test_normalize_keeps_international_digits():
    assert normalize_phone("+380501112233") == "380501112233"
