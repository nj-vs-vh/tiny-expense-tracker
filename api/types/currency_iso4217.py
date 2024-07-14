from dataclasses import dataclass


@dataclass
class CurrencyISO4217:
    """See iso4217.py for a list of instances of this class"""

    code: str  # 3-letter ISO code
    numeric_code: int
    name: str
    entities: list[str]  # countries etc
    precision: int
