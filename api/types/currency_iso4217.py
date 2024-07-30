from dataclasses import dataclass
from typing import Any


@dataclass
class CurrencyISO4217:
    """See iso4217.py for a list of instances of this class"""

    code: str  # 3-letter ISO code, uppercase
    numeric_code: int
    name: str
    entities: list[str]  # countries etc
    precision: int

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, CurrencyISO4217):
            return self.code == other.code
        return False

    def __hash__(self) -> int:
        return hash(self.code)

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}("{self.code}")'
