from api.iso4217 import CURRENCIES


def test_currencies_parsed() -> None:
    assert len(CURRENCIES) == 180
    assert "USD" in CURRENCIES
    assert "AMD" in CURRENCIES
