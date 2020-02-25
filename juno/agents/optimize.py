import logging
from decimal import Decimal
from typing import List, NamedTuple, Optional

from juno import Interval, Timestamp, strategies
from juno.modules import get_module_type
from juno.optimization import OptimizationSummary, Optimizer
from juno.trading import MissedCandlePolicy
from juno.typing import get_input_type_hints
from juno.utils import format_as_config

from .agent import Agent

_log = logging.getLogger(__name__)


class Optimize(Agent):
    def __init__(self, optimizer: Optimizer) -> None:
        super().__init__()
        self._optimizer = optimizer

    async def run(
        self,
        exchange: str,
        symbols: Optional[List[str]],
        intervals: Optional[List[Interval]],
        start: Timestamp,
        quote: Decimal,
        strategy: str,
        end: Optional[Timestamp] = None,
        missed_candle_policy: Optional[MissedCandlePolicy] = MissedCandlePolicy.IGNORE,
        trailing_stop: Optional[Decimal] = Decimal('0.0'),
        population_size: int = 50,
        max_generations: int = 1000,
        mutation_probability: Decimal = Decimal('0.2'),
        seed: Optional[int] = None,
        verbose: bool = False,
    ) -> None:
        strategy_type = get_module_type(strategies, strategy)
        self.result = OptimizationSummary()
        await self._optimizer.run(
            exchange=exchange,
            symbols=symbols,
            intervals=intervals,
            start=start,
            quote=quote,
            strategy_type=strategy_type,
            end=end,
            missed_candle_policy=missed_candle_policy,
            trailing_stop=trailing_stop,
            population_size=population_size,
            max_generations=max_generations,
            mutation_probability=mutation_probability,
            seed=seed,
            verbose=verbose,
            summary=self.result,
        )

    def on_finally(self) -> None:
        for ind in self.result.best:
            # Create a new typed named tuple for correctly formatting strategy kwargs for the
            # particular strategy type.
            strategy_kwargs_type_hints = get_input_type_hints(ind.trading_config.strategy_type)
            strategy_kwargs_type = NamedTuple('foo', strategy_kwargs_type_hints.items())  # type: ignore
            strategy_kwargs_instance = strategy_kwargs_type(*ind.trading_config.strategy_kwargs.values())

            trading_config_type_hints = get_input_type_hints(ind.trading_config)
            trading_config_type_hints['strategy_kwargs'] = strategy_kwargs_type
            trading_config_type = NamedTuple('bar', trading_config_type_hints.items())  # type: ignore
            x = ind.trading_config._asdict()
            x['strategy_kwargs'] = strategy_kwargs_instance
            trading_config_instance = trading_config_type(**x)

            # tc = ind.trading_config

            _log.info(f'trading config: {format_as_config(trading_config_instance)}')
            _log.info(f'trading summary: {format_as_config(ind.trading_summary)}')
            _log.info(f'portfolio stats: {format_as_config(ind.portfolio_stats)}')
