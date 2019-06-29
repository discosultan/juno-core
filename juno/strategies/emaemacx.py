import operator
from decimal import Decimal

from juno import Advice, Candle, Trend, math
from juno.indicators import Ema
from juno.utils import Persistence

from .strategy import Strategy


class EmaEmaCX(Strategy):

    def __init__(self, short_period: int, long_period: int, neg_threshold: Decimal,
                 pos_threshold: Decimal, persistence: int) -> None:
        if neg_threshold > 0.0 or pos_threshold < 0.0:
            raise ValueError(f'Neg threshold ({neg_threshold}) must be negative; pos threshold '
                             f'({pos_threshold}) positive')
        if long_period <= short_period:
            raise ValueError(f'Long period ({long_period}) must be bigger than short period '
                             f'({short_period})')

        self._ema_short = Ema(short_period)
        self._ema_long = Ema(long_period)
        self._neg_threshold = neg_threshold
        self._pos_threshold = pos_threshold
        self._persistence = Persistence(level=persistence, allow_initial_trend=False)
        self._t = 0
        self._t1 = long_period - 1

    @property
    def req_history(self) -> int:
        return self._t1

    @staticmethod
    def meta():
        return {
            ('short_period', 'long_period'): math.random_int_pair(1, 50, operator.lt, 2, 100),
            'neg_threshold': math.random_uniform(-1.0, -0.1),
            'pos_threshold': math.random_uniform(0.1, 1.0),
            'persistence': math.random_int(0, 10)
        }

    def update(self, candle: Candle) -> Advice:
        self._ema_short.update(candle.close)
        self._ema_long.update(candle.close)

        trend = Trend.UNKNOWN
        if self._t == self._t1:
            diff = 100 * (self._ema_short.value - self._ema_long.value) / ((
                self._ema_short.value + self._ema_long.value) / 2)

            if diff > self._pos_threshold:
                trend = Trend.UP
            elif diff < self._neg_threshold:
                trend = Trend.DOWN

        self._t = min(self._t + 1, self._t1)

        return advice(*self._persistence.update(trend))


def advice(trend: Trend, changed: bool) -> Advice:
    return {
        Trend.UP: Advice.BUY,
        Trend.DOWN: Advice.SELL
    }.get(trend, Advice.NONE) if changed else Advice.NONE
