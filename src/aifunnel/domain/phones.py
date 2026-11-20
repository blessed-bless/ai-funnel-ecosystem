import re

_DIGITS = re.compile(r"\D+")


def normalize_phone(raw: str | None) -> str | None:
    """Normalize RU/intl phones to 7XXXXXXXXXX when possible."""
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
