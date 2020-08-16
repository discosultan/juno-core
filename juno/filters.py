# Exchange filters.
# https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#filters

from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import NamedTuple

from .errors import OrderException


class Price(NamedTuple):
    min: Decimal = Decimal('0.0')
    max: Decimal = Decimal('0.0')  # 0 means disabled.
    step: Decimal = Decimal('0.0')  # 0 means disabled.

    def round_down(self, price: Decimal) -> Decimal:
        if price < self.min:
            return Decimal('0.0')

        if self.max > 0:
            price = min(price, self.max)
        if self.step > 0:
            price = price.quantize(self.step.normalize(), rounding=ROUND_DOWN)

        return price

    def valid(self, price: Decimal) -> bool:
        return (
            price >= self.min
            and (not self.max or price <= self.max)
            and (not self.step or (price - self.min) % self.step == 0)
        )


class PercentPrice(NamedTuple):
    multiplier_up: Decimal = Decimal('Inf')
    multiplier_down: Decimal = Decimal('0.0')
    avg_price_period: int = 0  # 0 means the last price is used.

    def valid(self, price: Decimal, weighted_average_price: Decimal) -> bool:
        return (
            price <= weighted_average_price * self.multiplier_up
            and price >= weighted_average_price * self.multiplier_down
        )


class Size(NamedTuple):
    min: Decimal = Decimal('0.0')
    max: Decimal = Decimal('0.0')  # 0 means disabled.
    step: Decimal = Decimal('0.0')  # 0 means disabled.

    def round_down(self, size: Decimal) -> Decimal:
        return self._round(size, ROUND_DOWN)

    def round_up(self, size: Decimal) -> Decimal:
        return self._round(size, ROUND_UP)

    def _round(self, size: Decimal, rounding: str) -> Decimal:
        if size < self.min:
            return Decimal('0.0')

        if self.max > 0:
            size = min(size, self.max)
        if self.step > 0:
            size = size.quantize(self.step.normalize(), rounding=rounding)

        return size

    def valid(self, size: Decimal) -> bool:
        return (
            size >= self.min
            and (not self.max or size <= self.max)
            and (not self.step or (size - self.min) % self.step == 0)
        )

    def validate(self, size: Decimal) -> None:
        if not self.valid(size):
            raise OrderException(
                f'Size {size} must be between [{self.min}; {self.max}] with a step of {self.step}'
            )


class MinNotional(NamedTuple):
    min_notional: Decimal = Decimal('0.0')
    apply_to_market: bool = False
    avg_price_period: int = 0  # 0 means the last price is used.

    def valid(self, price: Decimal, size: Decimal) -> bool:
        # For limit order only.
        return price * size >= self.min_notional

    def min_size_for_price(self, price: Decimal) -> Decimal:
        return self.min_notional / price

    def validate_limit(self, price: Decimal, size: Decimal) -> None:
        if not self.valid(price, size):
            raise OrderException(
                f'Price {price} * size {size} ({price * size}) must be between '
                f'[{self.min_notional}; inf]'
            )

    def validate_market(self, avg_price: Decimal, size: Decimal) -> None:
        if self.apply_to_market:
            self.validate_limit(avg_price, size)


class Filters(NamedTuple):
    price: Price = Price()
    percent_price: PercentPrice = PercentPrice()
    size: Size = Size()
    min_notional: MinNotional = MinNotional()

    base_precision: int = 8
    quote_precision: int = 8
    spot: bool = True
    cross_margin: bool = False
    isolated_margin: bool = False
