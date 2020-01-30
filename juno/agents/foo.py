import asyncio
import logging
from decimal import Decimal

from juno.asyncio import list_async
from juno.components import Chandler, Historian, Informant
from juno.math import floor_multiple
from juno.optimization import Optimizer, Rust
from juno.strategies import MAMACX
from juno.time import DAY_MS, strptimestamp
from juno.trading import Trader, TradingSummary, get_benchmark_statistics, get_portfolio_statistics

from .agent import Agent

_log = logging.getLogger(__name__)


class Foo(Agent):
    def __init__(self, chandler: Chandler, historian: Historian, informant: Informant) -> None:
        super().__init__()
        self._chandler = chandler
        self._informant = informant

    async def run(self) -> None:
        optimization_start = strptimestamp('2018-01-01')
        trading_start = strptimestamp('2019-07-01')
        end = strptimestamp('2020-01-01')
        exchange = 'binance'
        quote = Decimal('1.0')

        tickers = [t for t in self._informant.list_tickers(exchange) if t.symbol.endswith('-btc')]
        tickers.sort(key=lambda t: t.volume, reverse=True)
        assert len(tickers) > 5
        tickers = tickers[:5]
        symbols = [t.symbol for t in tickers]

        quote_per_symbol = quote / len(symbols)

        summary = TradingSummary(quote=quote, start=trading_start)
        await asyncio.gather(
            *(self._optimize_and_trade(
                exchange,
                s,
                optimization_start,
                trading_start,
                end,
                quote_per_symbol,
                summary,
            ) for s in symbols)
        )
        summary.finish(end)

        start_day = floor_multiple(start, DAY_MS)
        end_day = floor_multiple(end, DAY_MS)

        # Find first exchange which supports the fiat pair.
        # btc_fiat_symbol = 'btc-eur'
        # btc_fiat_exchange = 'coinbase'
        # btc_fiat_exchanges = self.informant.list_exchanges_supporting_symbol(btc_fiat_symbol)
        # if len(btc_fiat_exchanges) == 0:
        #     _log.warning(f'no exchange with fiat symbol {btc_fiat_symbol} found; skipping '
        #                  'calculating further statistics')
        #     return
        # btc_fiat_exchange = btc_fiat_exchanges[0]

        # Fetch necessary market data.
        btc_fiat_daily, symbol_daily = await asyncio.gather(
            list_async(self._chandler.stream_candles(
                'coinbase', 'btc-eur', DAY_MS, start_day, end_day
            )),
            *(list_async(self._chandler.stream_candles(
                exchange, s, DAY_MS, start_day, end_day
            )) for s in symbols),
        )

        benchmark_stats = get_benchmark_statistics(btc_fiat_daily)
        portfolio_stats = get_portfolio_statistics(
            benchmark_stats, btc_fiat_daily, symbol_daily, symbol, summary
        )

        _log.info(f'benchmark stats: {benchmark_stats}')
        _log.info(f'portfolio stats: {portfolio_stats}')

    async def _optimize_and_trade(
        self,
        exchange: str,
        symbol: str,
        optimization_start: int,
        trading_start: int,
        end: int,
        quote: Decimal,
        summary: TradingSummary
    ) -> None:
        optimizer = Optimizer(
            solver=Rust(),
            chandler=self._chandler,
            informant=self._informant,
            exchange=exchange,
            start=optimization_start,
            end=trading_start,
            quote=quote,
            strategy=MAMACX,
            symbols=[symbol],
            intervals=['30m', '1h', '2h'],
            population_size=50,
            max_generations=100
        )
        await optimizer.run()

        trader = Trader(
            chandler=self._chandler,
            informant=self._informant,
            exchange=exchange,
            symbol=symbol,
            interval=optimizer.result.interval,
            start=trading_start,
            end=end,
            quote=quote,
            new_strategy=lambda: MAMACX(**optimizer.result.strategy_config),
            missed_candle_policy=optimizer.result.missed_candle_policy,
            trailing_stop=optimizer.result.trailing_stop,
            summary=summary
        )
        await trader.run()
