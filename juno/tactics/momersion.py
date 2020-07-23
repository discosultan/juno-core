from decimal import Decimal
from typing import Dict

from juno import Candle, indicators
from juno.constraints import Constraint, Int, Uniform


class Momersion:
    class Meta:
        constraints: Dict[str, Constraint] = {
            'period': Int(1, 365),
            'threshold': Uniform(Decimal('0.01'), Decimal('99.99')),
        }

    _momersion: indicators.Momersion
    _threshold: Decimal

    def __init__(
        self,
        period: int = 28,
        threshold: Decimal = Decimal('0.50'),
    ) -> None:
        self._momersion = indicators.Momersion(period)
        self._threshold = threshold

    @property
    def maturity(self) -> int:
        return self._momersion.maturity

    def update(self, candle: Candle) -> None:
        self._momersion.update(candle.close)
        if self._momersion.mature:
            if self._momersion.value < self._threshold:
                # Non trending.
                pass
            else:
                # Trending.
                pass
