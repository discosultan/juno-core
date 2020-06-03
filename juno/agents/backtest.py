import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Dict, List, NamedTuple, Optional

from juno import Interval, Timestamp, strategies
from juno.components import Chandler, Events, Prices
from juno.config import (
    format_as_config, get_module_type_constructor, get_type_name_and_kwargs, kwargs_for
)
from juno.statistics import analyse_benchmark, analyse_portfolio
from juno.storages import Memory, Storage
from juno.time import DAY_MS, time_ms
from juno.traders import Trader
from juno.utils import extract_public

from .agent import Agent, AgentStatus

_log = logging.getLogger(__name__)


class Backtest(Agent):
    class Config(NamedTuple):
        exchange: str
        interval: Interval
        quote: Decimal
        trader: Dict[str, Any]
        strategy: Dict[str, Any]
        name: Optional[str] = None
        persist: bool = False
        start: Optional[Timestamp] = None
        end: Optional[Timestamp] = None
        fiat_exchange: Optional[str] = None
        fiat_asset: str = 'usdt'

    @dataclass
    class State:
        name: str
        status: AgentStatus
        result: Optional[Any] = None

    def __init__(
        self,
        traders: List[Trader],
        chandler: Chandler,
        prices: Optional[Prices] = None,
        events: Events = Events(),
        storage: Storage = Memory(),
        get_time_ms: Callable[[], int] = time_ms,
    ) -> None:
        self._traders = {type(t).__name__.lower(): t for t in traders}
        self._chandler = chandler
        self._prices = prices
        self._events = events
        self._storage = storage
        self._get_time_ms = get_time_ms

    async def on_running(self, config: Config, state: State) -> None:
        await super().on_running(config, state)

        now = self._get_time_ms()

        assert config.start is None or config.start < now
        assert config.end is None or config.end <= now
        assert config.start is None or config.end is None or config.start < config.end

        start = config.start
        end = now if config.end is None else config.end

        trader_name, trader_kwargs = get_type_name_and_kwargs(config.trader)
        trader = self._traders[trader_name]
        trader_config = trader.Config(
            exchange=config.exchange,
            interval=config.interval,
            start=start,
            end=end,
            quote=config.quote,
            strategy=get_module_type_constructor(strategies, config.strategy),
            channel=state.name,
            test=True,
            **kwargs_for(trader.Config, trader_kwargs),
        )
        if not state.result:
            state.result = trader.State()

        await trader.run(trader_config, state.result)
        assert (summary := state.result.summary)

        if not self._prices:
            _log.warning('skipping analysis; prices component not available')
            return

        # Fetch necessary market data.
        symbols = (
            [p.symbol for p in summary.get_positions()]
            + [f'btc-{config.fiat_asset}']  # Use BTC as benchmark.
        )
        analysis_interval = max(DAY_MS, config.interval)
        fiat_prices = await self._prices.map_prices(
            exchange=config.exchange,
            symbols=symbols,
            start=summary.start,
            end=summary.end,
            interval=analysis_interval,
            fiat_asset=config.fiat_asset,
            fiat_exchange=config.fiat_exchange,
        )

        benchmark = analyse_benchmark(fiat_prices['btc'])
        portfolio = analyse_portfolio(
            benchmark_g_returns=benchmark.g_returns,
            fiat_prices=fiat_prices,
            trading_summary=summary,
            interval=analysis_interval,
        )

        _log.info(f'benchmark stats: {format_as_config(benchmark.stats)}')
        _log.info(f'portfolio stats: {format_as_config(portfolio.stats)}')

    async def on_finally(self, config: Config, state: State) -> None:
        assert state.result
        _log.info(
            f'{self.get_name(state)}: finished with result '
            f'{format_as_config(extract_public(state.result.summary))}'
        )
        await self._events.emit(state.name, 'finished', state.result.summary)
