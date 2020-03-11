import asyncio
import logging
from decimal import Decimal

from juno import components, exchanges, optimization, storages, strategies, time
from juno.config import from_env, init_instance
from juno.math import floor_multiple
from juno.trading import MissedCandlePolicy, Trader, analyse_benchmark, analyse_portfolio
from juno.utils import unpack_symbol

SYMBOL = 'eth-btc'
INTERVAL = time.HOUR_MS
START = time.strptimestamp('2017-07-14')
END = time.strptimestamp('2019-12-07')
MISSED_CANDLE_POLICY = MissedCandlePolicy.LAST
TRAILING_STOP = Decimal('0.8486')

SHORT_PERIOD = 7
LONG_PERIOD = 49
NEG_THRESHOLD = Decimal('-0.946')
POS_THRESHOLD = Decimal('0.854')
PERSISTENCE = 6
SHORT_MA = 'smma'
LONG_MA = 'sma'

# SYMBOL = 'enj-bnb'  # NB! Non-btc quote not supported in prices!
# INTERVAL = time.DAY_MS
# START = time.strptimestamp('2019-01-01')
# END = time.strptimestamp('2019-12-22')
# MISSED_CANDLE_POLICY = MissedCandlePolicy.LAST
# TRAILING_STOP = Decimal('0.0')

# SHORT_PERIOD = 1
# LONG_PERIOD = 8
# NEG_THRESHOLD = Decimal('-0.624')
# POS_THRESHOLD = Decimal('0.893')
# PERSISTENCE = 2
# SHORT_MA = 'smma'
# LONG_MA = 'smma'


async def main() -> None:
    start = floor_multiple(START, INTERVAL)
    end = floor_multiple(END, INTERVAL)

    storage = storages.SQLite()
    binance = init_instance(exchanges.Binance, from_env())
    coinbase = init_instance(exchanges.Coinbase, from_env())
    exchange_list = [binance, coinbase]
    informant = components.Informant(storage, exchange_list)
    trades = components.Trades(storage, exchange_list)
    chandler = components.Chandler(trades=trades, storage=storage, exchanges=exchange_list)
    prices = components.Prices(chandler)
    trader = Trader(chandler=chandler, informant=informant)
    rust_solver = optimization.Rust()
    python_solver = optimization.Python()
    async with binance, coinbase, informant, rust_solver:
        candles = await chandler.list_candles('binance', SYMBOL, INTERVAL, start, end)
        fiat_daily_prices = await prices.map_fiat_daily_prices(
            ('btc', unpack_symbol(SYMBOL)[0]), start, end
        )
        benchmark = analyse_benchmark(fiat_daily_prices['btc'])
        fees, filters = informant.get_fees_filters('binance', SYMBOL)

        logging.info('running backtest in rust solver, python solver, python trader ...')

        args = (
            fiat_daily_prices,
            benchmark.g_returns,
            strategies.MAMACX,
            start,
            end,
            Decimal('1.0'),
            candles,
            fees,
            filters,
            SYMBOL,
            INTERVAL,
            MISSED_CANDLE_POLICY,
            TRAILING_STOP,
            SHORT_PERIOD,
            LONG_PERIOD,
            NEG_THRESHOLD,
            POS_THRESHOLD,
            PERSISTENCE,
            SHORT_MA,
            LONG_MA,
        )
        rust_result = rust_solver.solve(*args)
        python_result = python_solver.solve(*args)

        trading_summary = await trader.run(Trader.Config(
            'binance',
            SYMBOL,
            INTERVAL,
            start,
            end,
            Decimal('1.0'),
            strategy='mamacx',
            strategy_kwargs={
                'short_period': SHORT_PERIOD,
                'long_period': LONG_PERIOD,
                'neg_threshold': NEG_THRESHOLD,
                'pos_threshold': POS_THRESHOLD,
                'persistence': PERSISTENCE,
                'short_ma': SHORT_MA,
                'long_ma': LONG_MA,
            },
            missed_candle_policy=MISSED_CANDLE_POLICY,
            trailing_stop=TRAILING_STOP,
            adjust_start=False,
        ))
        portfolio = analyse_portfolio(
            benchmark.g_returns, fiat_daily_prices, trading_summary
        )

        logging.info('=== rust solver ===')
        logging.info(f'alpha {rust_result.alpha}')
        # logging.info(f'profit {rust_result.profit}')
        # logging.info(f'mean pos dur {rust_result.mean_position_duration}')

        logging.info('=== python solver ===')
        logging.info(f'alpha {python_result.alpha}')
        # logging.info(f'profit {python_result.profit}')
        # logging.info(f'mean pos dur {python_result.mean_position_duration}')

        logging.info('=== python trader ===')
        logging.info(f'alpha {portfolio.stats.alpha}')
        logging.info(f'profit {trading_summary.profit}')
        logging.info(f'mean pos dur {trading_summary.mean_position_duration}')


asyncio.run(main())
