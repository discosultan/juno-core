import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from uuid import uuid4

from juno import (
    AssetInfo,
    BorrowInfo,
    Depth,
    ExchangeInfo,
    Fees,
    Filters,
    OrderResult,
    OrderStatus,
    candles,
    components,
    exchanges,
    storages,
    trades,
)
from juno.candles import Candle


class Exchange(exchanges.Exchange):
    can_stream_balances: bool = True
    can_stream_depth_snapshot: bool = True
    can_list_all_tickers: bool = True
    can_margin_trade: bool = True
    can_place_market_order: bool = True
    can_place_market_order_quote: bool = True

    def __init__(
        self,
        exchange_info=ExchangeInfo(),
        tickers={},
        balances={'spot': {}},
        future_balances=[],
        depth=Depth.Snapshot(),
        future_depths=[],
        future_orders=[],
        place_order_result=OrderResult(time=0, status=OrderStatus.NEW),
        client_id=str(uuid4()),
    ):
        super().__init__()

        self.exchange_info = exchange_info
        self.get_exchange_info_calls = []
        self.tickers = tickers

        self.balances = balances
        self.balance_queue = asyncio.Queue()
        for future_balance in future_balances:
            self.balance_queue.put_nowait(future_balance)

        self.depth = depth
        self.depth_queue = asyncio.Queue()
        for future_depth in future_depths:
            self.depth_queue.put_nowait(future_depth)

        self.orders_queue = asyncio.Queue()
        for future_order in future_orders:
            self.orders_queue.put_nowait(future_order)

        self.place_order_result = place_order_result
        self.place_order_calls = []

        self.cancel_order_calls = []

        self.client_id = client_id

    def generate_client_id(self):
        return self.client_id

    async def get_exchange_info(self):
        result = self.exchange_info
        self.get_exchange_info_calls.append([result])
        return result

    async def map_tickers(self):
        return self.tickers

    async def map_balances(self, account):
        return self.balances

    @asynccontextmanager
    async def connect_stream_balances(self, account):
        yield _stream_queue(self.balance_queue)

    async def get_depth(self, symbol):
        return self.depth

    @asynccontextmanager
    async def connect_stream_depth(self, symbol):
        yield _stream_queue(self.depth_queue)

    @asynccontextmanager
    async def connect_stream_orders(self, symbol, account):
        yield _stream_queue(self.orders_queue)

    async def place_order(self, *args, **kwargs):
        await asyncio.sleep(0)
        # TODO: We are ignoring *args
        self.place_order_calls.append(kwargs)
        return self.place_order_result

    async def cancel_order(self, *args, **kwargs):
        await asyncio.sleep(0)
        self.cancel_order_calls.append(kwargs)


async def _stream_queue(queue):
    while True:
        item = await queue.get()
        queue.task_done()
        if isinstance(item, Exception):
            raise item
        yield item


class Chandler(candles.Chandler):
    def __init__(
        self,
        candles={},
        future_candles={},
        first_candle=Candle(),
        last_candle=Candle(),
        candle_intervals={},
    ):
        self.candles = candles
        self.future_candle_queues = defaultdict(asyncio.Queue)
        for k, cl in future_candles.items():
            future_candle_queue = self.future_candle_queues[k]
            for c in cl:
                future_candle_queue.put_nowait(c)
        self.first_candle = first_candle
        self.last_candle = last_candle
        self.candle_intervals = candle_intervals

    async def stream_candles(
        self, exchange, symbol, interval, start, end, closed=True, fill_missing_with_last=False,
        simulate_open_from_interval=None, exchange_timeout=None
    ):
        # TODO: Get rid of this!
        if candles := self.candles.get((exchange, symbol, interval)):
            last_c = None
            for c in (c for c in candles if c.time >= start and c.time < end):
                time_diff = c.time - last_c.time if last_c else 0
                if time_diff >= interval * 2:
                    num_missed = time_diff // interval - 1
                    if fill_missing_with_last:
                        for i in range(1, num_missed + 1):
                            yield Candle(
                                time=last_c.time + i * interval,
                                open=last_c.open,
                                high=last_c.high,
                                low=last_c.low,
                                close=last_c.close,
                                volume=last_c.volume,
                                closed=True,
                            )
                if not closed or c.closed:
                    yield c
                last_c = c

        if future_candles := self.future_candle_queues.get((exchange, symbol, interval)):
            while True:
                candle = await future_candles.get()
                future_candles.task_done()
                yield candle
                if candle.time >= end - interval:
                    break

    async def get_first_candle(self, exchange, symbol, interval):
        return self.first_candle

    async def get_last_candle(self, exchange, symbol, interval):
        return self.last_candle

    def map_candle_intervals(self, exchange, patterns=None):
        return self.candle_intervals

    def get_interval_offset(self, exchange, interval):
        return 0


class Trades(trades.Trades):
    def __init__(self, trades=[]):
        self.trades = trades

    async def stream_trades(self, exchange, symbol, start, end):
        for t in (t for t in self.trades if t.time >= start and t.time < end):
            yield t


class Informant(components.Informant):
    def __init__(
        self,
        fees=Fees(),
        filters=Filters(),
        symbols=[],
        tickers={},
        exchanges=[],
        borrow_info=BorrowInfo(),
        margin_multiplier=2,
        assets=[],
        asset_info=AssetInfo(),
    ):
        self.fees = fees
        self.filters = filters
        self.symbols = symbols
        self.tickers = tickers
        self.exchanges = exchanges
        self.borrow_info = borrow_info
        self.margin_multiplier = margin_multiplier
        self.assets = assets
        self.asset_info = asset_info

    def get_asset_info(self, exchange, asset):
        return self.asset_info

    def get_borrow_info(self, account, exchange, asset):
        return self.borrow_info

    def get_margin_multiplier(self, exchange):
        return self.margin_multiplier

    def get_fees_filters(self, exchange, symbol):
        return self.fees, self.filters

    def list_assets(self, exchange, borrow=False):
        return self.assets

    def list_symbols(
        self, exchange, patterns=None, spot=True, cross_margin=False, isolated_margin=False
    ):
        return self.symbols

    def map_tickers(
        self, exchange, symbol_patterns=None, exclude_symbol_patterns=None, spot=True,
        cross_margin=False, isolated_margin=False
    ):
        return self.tickers

    def list_exchanges(self, exchange, symbol=None):
        return self.exchanges


class Time:
    def __init__(self, time=0, increment=0):
        self.time = time
        self.increment = increment

    def get_time(self):
        time = self.time
        self.time += self.increment
        return time


class Storage(storages.Memory):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stored_time_series_and_span = asyncio.Event()
        self.store_time_series_and_span_calls = []
        self.get_calls = []
        self.set_calls = []

    async def store_time_series_and_span(self, shard, key, items, start, end):
        await super().store_time_series_and_span(shard, key, items, start, end)
        self.store_time_series_and_span_calls.append((shard, key, items, start, end))
        self.stored_time_series_and_span.set()
        await asyncio.sleep(0)

    async def get(self, shard, key, type_):
        result = await super().get(shard, key, type_)
        self.get_calls.append((shard, key, type_, result))
        return result

    async def set(self, shard, key, item):
        await super().set(shard, key, item)
        self.set_calls.append((shard, key, item, None))
