import re


_DIGITS = re.compile(r"\D+")


def normalize_phone(raw: str | None) -> str | None:
    """Нормализация RU/международных номеров к виду 7XXXXXXXXXX когда возможно."""
    if not raw:
        return None
    digits = _DIGITS.sub("", raw)
    if not digits:
        return None
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    return digits
