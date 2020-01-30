from __future__ import annotations

import asyncio
import logging
import sys
from decimal import Decimal
from typing import AsyncIterable, Callable, List, Optional

from tenacity import Retrying, before_sleep_log, retry_if_exception_type

from juno import Candle, JunoException
from juno.asyncio import list_async
from juno.exchanges import Exchange
from juno.math import floor_multiple
from juno.storages import Storage
from juno.tenacity import stop_after_attempt_with_reset
from juno.time import strfinterval, strfspan, strftimestamp, time_ms
from juno.utils import generate_missing_spans, merge_adjacent_spans, unpack_symbol

from .informant import Informant
from .trades import Trades

_log = logging.getLogger(__name__)


class Chandler:
    def __init__(
        self,
        storage: Storage,
        exchanges: List[Exchange],
        informant: Optional[Informant] = None,
        trades: Optional[Trades] = None,
        get_time_ms: Callable[[], int] = time_ms,
        storage_batch_size: int = 1000
    ) -> None:
        assert storage_batch_size > 0

        self._storage = storage
        self._exchanges = {type(e).__name__.lower(): e for e in exchanges}
        self._informant = informant
        self._trades = trades
        self._get_time_ms = get_time_ms
        self._storage_batch_size = storage_batch_size

    async def list_candles(self, *args, **kwargs) -> List[Candle]:
        return await list_async(self.stream_candles(*args, **kwargs))

    async def stream_candles(
        self, exchange: str, symbol: str, interval: int, start: int, end: int, closed: bool = True,
        fill_missing_with_last: bool = False
    ) -> AsyncIterable[Candle]:
        """Tries to stream candles for the specified range from local storage. If candles don't
        exist, streams them from an exchange and stores to local storage."""
        storage_key = (exchange, symbol, interval)
        candle_msg = f'{exchange} {symbol} {strfinterval(interval)} candle(s)'

        _log.info(f'checking for existing {candle_msg} in local storage')
        existing_spans = await list_async(
            self._storage.stream_time_series_spans(storage_key, Candle, start, end)
        )
        merged_existing_spans = list(merge_adjacent_spans(existing_spans))
        missing_spans = list(generate_missing_spans(start, end, merged_existing_spans))

        spans = ([(a, b, True) for a, b in merged_existing_spans] + [(a, b, False)
                                                                     for a, b in missing_spans])
        spans.sort(key=lambda s: s[0])

        last_closed_candle: Optional[Candle] = None
        for span_start, span_end, exist_locally in spans:
            period_msg = f'{strfspan(span_start, span_end)}'
            if exist_locally:
                _log.info(f'local {candle_msg} exist between {period_msg}')
                stream = self._storage.stream_time_series(
                    storage_key, Candle, span_start, span_end
                )
            else:
                _log.info(f'missing {candle_msg} between {period_msg}')
                stream = self._stream_and_store_exchange_candles(
                    exchange, symbol, interval, span_start, span_end
                )
            async for candle in stream:
                if not last_closed_candle and candle.closed:
                    num_missed = (candle.time - start) // interval
                    if num_missed > 0:
                        _log.warning(
                            f'missed {num_missed} {candle_msg} from the start '
                            f'{strftimestamp(start)}; current candle {candle}'
                        )

                # TODO: use walrus operator
                time_diff = candle.time - last_closed_candle.time if last_closed_candle else 0
                if time_diff >= interval * 2:
                    assert last_closed_candle
                    num_missed = time_diff // interval - 1
                    _log.warning(
                        f'missed {num_missed} {candle_msg}; last closed candle '
                        f'{last_closed_candle}; current candle {candle}'
                    )
                    if fill_missing_with_last:
                        _log.info(f'filling {num_missed} missed {candle_msg} with last values')
                        for i in range(1, num_missed + 1):
                            yield Candle(
                                time=last_closed_candle.time + i * interval,
                                open=last_closed_candle.open,
                                high=last_closed_candle.high,
                                low=last_closed_candle.low,
                                close=last_closed_candle.close,
                                volume=last_closed_candle.volume,
                                closed=True
                            )
                if not closed or candle.closed:
                    yield candle
                if candle.closed:
                    last_closed_candle = candle

        if not last_closed_candle:
            _log.warning(f'missed all {candle_msg} between {strfspan(start, end)}')
        else:
            time_diff = end - last_closed_candle.time
            if time_diff >= interval * 2:
                num_missed = time_diff // interval - 1
                _log.warning(
                    f'missed {num_missed} {candle_msg} from the end {strftimestamp(end)}; '
                    f'current candle {candle}'
                )

    async def _stream_and_store_exchange_candles(
        self, exchange: str, symbol: str, interval: int, start: int, end: int
    ) -> AsyncIterable[Candle]:
        storage_key = (exchange, symbol, interval)
        # Note that we need to use a context manager based retrying because retry decorators do not
        # work with async generator functions.
        for attempt in Retrying(
            stop=stop_after_attempt_with_reset(3, 300),
            retry=retry_if_exception_type(JunoException),
            before_sleep=before_sleep_log(_log, logging.DEBUG)
        ):
            with attempt:
                batch = []
                swap_batch: List[Candle] = []
                batch_start = start
                current = floor_multiple(self._get_time_ms(), interval)

                try:
                    async for candle in self._stream_exchange_candles(
                        exchange=exchange,
                        symbol=symbol,
                        interval=interval,
                        start=start,
                        end=end,
                        current=current
                    ):
                        if candle.closed:
                            batch.append(candle)
                            if len(batch) == self._storage_batch_size:
                                batch_end = batch[-1].time + interval
                                batch, swap_batch = swap_batch, batch
                                await self._storage.store_time_series_and_span(
                                    key=storage_key,
                                    type_=Candle,
                                    items=swap_batch,
                                    start=batch_start,
                                    end=batch_end,
                                )
                                batch_start = batch_end
                                del swap_batch[:]
                        yield candle
                except (asyncio.CancelledError, JunoException):
                    if len(batch) > 0:
                        batch_end = batch[-1].time + interval
                        await self._storage.store_time_series_and_span(
                            key=storage_key,
                            type_=Candle,
                            items=batch,
                            start=batch_start,
                            end=batch_end,
                        )
                        start = batch_end
                    raise
                else:
                    current = floor_multiple(self._get_time_ms(), interval)
                    batch_end = min(current, end)
                    await self._storage.store_time_series_and_span(
                        key=storage_key,
                        type_=Candle,
                        items=batch,
                        start=batch_start,
                        end=batch_end,
                    )

    async def _stream_exchange_candles(
        self, exchange: str, symbol: str, interval: int, start: int, end: int, current: int
    ) -> AsyncIterable[Candle]:
        exchange_instance = self._exchanges[exchange]
        # If informant is not available, we assume the interval to be supported. We will fail in
        # exchange if it is not.
        is_candle_interval_supported = (
            not self._informant or interval in self._informant.list_candle_intervals(exchange)
        )

        async def inner(stream: Optional[AsyncIterable[Candle]]) -> AsyncIterable[Candle]:
            if start < current:  # Historical.
                historical_end = min(end, current)
                if (
                    exchange_instance.can_stream_historical_candles
                    and is_candle_interval_supported
                ):
                    async for candle in exchange_instance.stream_historical_candles(
                        symbol, interval, start, historical_end
                    ):
                        yield candle
                else:
                    async for candle in self._stream_construct_candles(
                        exchange, symbol, interval, start, historical_end
                    ):
                        yield candle
            if stream:  # Future.
                async for candle in stream:
                    if candle.time >= end:
                        break

                    yield candle

                    if candle.closed and candle.time == end - interval:
                        break

        if end > current:
            if exchange_instance.can_stream_candles and is_candle_interval_supported:
                async with exchange_instance.connect_stream_candles(symbol, interval) as stream:
                    async for candle in inner(stream):
                        yield candle
            else:
                stream = self._stream_construct_candles(exchange, symbol, interval, current, end)
                async for candle in inner(stream):
                    yield candle
        else:
            async for candle in inner(None):
                yield candle

    async def _stream_construct_candles(
        self, exchange: str, symbol: str, interval: int, start: int, end: int
    ) -> AsyncIterable[Candle]:
        if not self._trades:
            raise ValueError('Trades component not configured. Unable to construct candles')

        _log.info(f'constructing {exchange} {symbol} {interval} candles from trades')

        current = start
        next_ = current + interval
        open_ = Decimal('0.0')
        high = Decimal('0.0')
        low = Decimal(f'{sys.maxsize}.0')
        close = Decimal('0.0')
        volume = Decimal('0.0')
        is_first = True
        async for trade in self._trades.stream_trades(exchange, symbol, start, end):
            if trade.time >= next_:
                assert not is_first
                yield Candle(
                    time=current,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    closed=True
                )
                current = next_
                next_ = current + interval
                open_ = Decimal('0.0')
                high = Decimal('0.0')
                low = Decimal(f'{sys.maxsize}.0')
                close = Decimal('0.0')
                volume = Decimal('0.0')
                is_first = True

            if is_first:
                open_ = trade.price
                is_first = False
            high = max(high, trade.price)
            low = min(low, trade.price)
            close = trade.price
            volume += trade.size

        if not is_first:
            yield Candle(
                time=current,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                closed=True
            )

    async def _stream_construct_candles_by_volume(
        self, exchange: str, symbol: str, volume: Decimal, start: int, end: int
    ) -> AsyncIterable[Candle]:
        if not self._trades:
            raise ValueError('Trades component not configured. Unable to construct candles')

        base_asset, _ = unpack_symbol(symbol)
        _log.info(f'constructing {exchange} {symbol} {volume}{base_asset} candles from trades')

        current_volume = Decimal('0.0')
        is_first = True
        async for trade in self._trades.stream_trades(exchange, symbol, start, end):
            if is_first:
                is_first = False
                time = trade.time
                open_ = trade.price
                high = trade.price
                low = trade.price
                close = trade.price
            else:
                high = max(high, trade.price)
                low = min(low, trade.price)
                close = trade.price

            current_volume += trade.size
            while current_volume > volume:
                yield Candle(
                    time=time,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    closed=True
                )
                current_volume -= volume
                time = trade.time
                open_ = trade.price
                high = trade.price
                low = trade.price
                close = trade.price
