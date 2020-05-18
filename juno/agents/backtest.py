import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, NamedTuple, Optional, TypeVar

from juno import Interval, MissedCandlePolicy, Timestamp
from juno.components import Chandler, Events, Prices
from juno.config import get_type_name_and_kwargs
from juno.math import floor_multiple
from juno.statistics import analyse_benchmark, analyse_portfolio
from juno.storages import Memory, Storage
from juno.strategies import Strategy
from juno.time import strftimestamp, time_ms
from juno.traders import Basic
from juno.utils import format_as_config, unpack_symbol

from .agent import Agent, AgentStatus

_log = logging.getLogger(__name__)

TStrategy = TypeVar('TStrategy', bound=Strategy)


class Backtest(Agent):
    class Config(NamedTuple):
        exchange: str
        symbol: str
        interval: Interval
        quote: Decimal
        strategy: Dict[str, Any]
        name: Optional[str] = None
        persist: bool = False
        start: Optional[Timestamp] = None
        end: Optional[Timestamp] = None
        missed_candle_policy: MissedCandlePolicy = MissedCandlePolicy.IGNORE
        adjust_start: bool = True
        trailing_stop: Decimal = Decimal('0.0')
        long: bool = True
        short: bool = False
        fiat_exchange: Optional[str] = None
        fiat_asset: str = 'usdt'

        @property
        def base_asset(self) -> str:
            return unpack_symbol(self.symbol)[0]

        @property
        def quote_asset(self) -> str:
            return unpack_symbol(self.symbol)[1]

    @dataclass
    class State:
        name: str
        status: AgentStatus
        result: Optional[Any] = None

    def __init__(
        self,
        trader: Basic,
        chandler: Chandler,
        prices: Optional[Prices] = None,
        events: Events = Events(),
        storage: Storage = Memory(),
    ) -> None:
        self._trader = trader
        self._chandler = chandler
        self._prices = prices
        self._events = events
        self._storage = storage

    async def on_running(self, config: Config, state: State) -> None:
        await super().on_running(config, state)

        start = config.start
        first_candle = await self._chandler.find_first_candle(
            config.exchange, config.symbol, config.interval
        )
        if start is None or start < first_candle.time:
            start = first_candle.time
            _log.info(f'start not specified; start set to {strftimestamp(start)}')

        now = time_ms()

        start = floor_multiple(start, config.interval)
        end = config.end
        if end is None:
            end = now
        end = floor_multiple(end, config.interval)

        assert end <= now
        assert end > start
        assert config.quote > 0

        strategy_name, strategy_kwargs = get_type_name_and_kwargs(config.strategy)
        trader_config = Basic.Config(
            exchange=config.exchange,
            symbol=config.symbol,
            interval=config.interval,
            start=start,
            end=end,
            quote=config.quote,
            strategy=strategy_name,
            strategy_kwargs=strategy_kwargs,
            channel=state.name,
            missed_candle_policy=config.missed_candle_policy,
            adjust_start=config.adjust_start,
            trailing_stop=config.trailing_stop,
            long=config.long,
            short=config.short,
        )
        if not state.result:
            state.result = Basic.State()
        await self._trader.run(trader_config, state.result)
        assert (summary := state.result.summary)

        if not self._prices:
            _log.warning('skipping analysis; prices component not available')
            return

        # Fetch necessary market data.
        symbols = (
            [p.symbol for p in summary.get_positions()]
            + [f'btc-{config.fiat_asset}']  # Use BTC as benchmark.
        )
        fiat_daily_prices = await self._prices.map_prices(
            exchange=config.exchange,
            symbols=symbols,
            fiat_asset=config.fiat_asset,
            fiat_exchange=config.fiat_exchange,
            start=summary.start,
            end=summary.end,
        )

        benchmark = analyse_benchmark(fiat_daily_prices['btc'])
        portfolio = analyse_portfolio(benchmark.g_returns, fiat_daily_prices, summary)

        _log.info(f'benchmark stats: {format_as_config(benchmark.stats)}')
        _log.info(f'portfolio stats: {format_as_config(portfolio.stats)}')

    async def on_finally(self, config: Config, state: State) -> None:
        assert state.result
        _log.info(
            f'{self.get_name(state)}: finished with result '
            f'{format_as_config(state.result.summary)}'
        )
        await self._events.emit(state.name, 'finished', state.result.summary)
