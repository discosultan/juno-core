from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Callable, NamedTuple, Type

from juno.strategies import Strategy
from juno.time import strfinterval
from juno.trading import TradingSummary


class Solver(ABC):
    @abstractmethod
    async def get(
        self,
        strategy_type: Type[Strategy],
        exchange: str,
        symbol: str,
        interval: int,
        start: int,
        end: int,
        quote: Decimal,
    ) -> Callable[..., Any]:
        pass


class SolverResult(NamedTuple):
    profit: float
    mean_drawdown: float
    max_drawdown: float
    mean_position_profit: float
    mean_position_duration: int

    def __repr__(self) -> str:
        return (
            f'{type(self).__name__}(profit={self.profit}, mean_drawdown={self.mean_drawdown:.1%}, '
            f'max_drawdown={self.max_drawdown:.1%}, '
            f'mean_position_profit={self.mean_position_profit}, '
            f'mean_position_duration={strfinterval(self.mean_position_duration)})'
        )

    @staticmethod
    def from_trading_summary(summary: TradingSummary) -> SolverResult:
        return SolverResult(
            float(summary.profit),
            float(summary.mean_drawdown),
            float(summary.max_drawdown),
            float(summary.mean_position_profit),
            summary.mean_position_duration,
        )
