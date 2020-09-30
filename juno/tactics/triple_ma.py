import operator
from typing import Dict, Tuple, Union

from juno import Advice, Candle, indicators
from juno.constraints import Constraint, Int, Triple
from juno.indicators import MA, Ema
from juno.utils import get_module_type

from .common import ma_choices


# Signals long when shorter average crosses above the longer.
# Signals short when shorter average crosses below the longer.
# J. Murphy 204
class TripleMA:
    class Meta:
        constraints: Dict[Union[str, Tuple[str, ...]], Constraint] = {
            'short_ma': ma_choices,
            'medium_ma': ma_choices,
            'long_ma': ma_choices,
            ('short_period', 'medium_period', 'long_period'): Triple(
                Int(1, 99),
                operator.lt,
                Int(2, 100),
                operator.lt,
                Int(3, 101),
            ),
        }

    _short_ma: MA
    _medium_ma: MA
    _long_ma: MA
    _advice: Advice = Advice.NONE

    def __init__(
        self,
        short_ma: str = Ema.__name__.lower(),
        medium_ma: str = Ema.__name__.lower(),
        long_ma: str = Ema.__name__.lower(),
        short_period: int = 4,  # Common 4 or 5. Daily.
        medium_period: int = 9,  # Common 9 or 10.
        long_period: int = 18,  # Common 18 or 20.
    ) -> None:
        assert short_period < medium_period < long_period
        self._short_ma = get_module_type(indicators, short_ma)(short_period)
        self._medium_ma = get_module_type(indicators, medium_ma)(medium_period)
        self._long_ma = get_module_type(indicators, long_ma)(long_period)

    @property
    def maturity(self) -> int:
        return self._long_ma.maturity

    def update(self, candle: Candle) -> Advice:
        self._short_ma.update(candle.close)
        self._medium_ma.update(candle.close)
        self._long_ma.update(candle.close)

        if self._long_ma.mature:
            if (
                self._short_ma.value > self._medium_ma.value
                and self._medium_ma.value > self._long_ma.value
            ):
                self._advice = Advice.LONG
            elif (
                self._short_ma.value < self._medium_ma.value
                and self._medium_ma.value < self._long_ma.value
            ):
                self._advice = Advice.SHORT
            elif (
                self._advice is Advice.SHORT
                and self._short_ma.value > self._medium_ma.value
                and self._short_ma.value > self._long_ma.value
            ):
                self._advice = Advice.LIQUIDATE
            elif (
                self._advice is Advice.LONG
                and self._short_ma.value < self._medium_ma.value
                and self._short_ma.value < self._long_ma.value
            ):
                self._advice = Advice.LIQUIDATE

        return self._advice
