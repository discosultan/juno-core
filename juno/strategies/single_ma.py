from decimal import Decimal

from juno import Advice, Candle, indicators
from juno.constraints import Int
from juno.indicators import MA, Ema
from juno.utils import get_module_type

from .strategy import Meta, Strategy, ma_choices


# Signals a long position when a candle close price goes above moving average and moving average is
# ascending.
# Signals a short position when a candle close price goes below moving average and moving average
# is descending.
class SingleMA(Strategy):
    @staticmethod
    def meta() -> Meta:
        return Meta(
            constraints={
                'ma': ma_choices,
                'period': Int(1, 100),
                'persistence': Int(0, 10),
            }
        )

    _ma: MA
    _previous_ma_value: Decimal = Decimal('0.0')
    _advice: Advice = Advice.NONE

    def __init__(
        self,
        ma: str = Ema.__name__.lower(),
        period: int = 50,
        persistence: int = 0,
    ) -> None:
        self._ma = get_module_type(indicators, ma)(period)
        super().__init__(
            maturity=self._ma.maturity, persistence=persistence, ignore_mid_trend=True
        )

    def tick(self, candle: Candle) -> Advice:
        self._ma.update(candle.close)

        if self.mature:
            if candle.close > self._ma.value and self._ma.value > self._previous_ma_value:
                self._advice = Advice.LONG
            elif candle.close < self._ma.value and self._ma.value < self._previous_ma_value:
                self._advice = Advice.SHORT
            else:
                self._advice = Advice.NONE

        self._previous_ma_value = self._ma.value
        return self._advice
