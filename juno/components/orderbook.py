from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from decimal import Decimal
from itertools import product
from typing import Any, AsyncIterable, Dict, List, Tuple, Union

import backoff

from juno import DepthSnapshot, DepthUpdate, Side
from juno.asyncio import Barrier, Event, cancel, cancelable
from juno.config import list_names
from juno.exchanges import Exchange
from juno.typing import ExcType, ExcValue, Traceback

_log = logging.getLogger(__name__)


class Orderbook:
    def __init__(self, exchanges: List[Exchange], config: Dict[str, Any]) -> None:
        self._exchanges = {type(e).__name__.lower(): e for e in exchanges}
        self._symbols = list_names(config, 'symbol')
        self._orderbooks_product = list(product(self._exchanges.keys(), self._symbols))

        # {
        #   "binance": {
        #     "eth-btc": {
        #       "asks": {
        #         Decimal(1): Decimal(2)
        #       },
        #       "bids": {
        #       }
        #     }
        #   }
        # }
        self._data: Dict[str, Dict[str, _OrderbookData]] = defaultdict(
            lambda: defaultdict(_OrderbookData)
        )

    async def __aenter__(self) -> Orderbook:
        self._initial_orderbook_fetched = Barrier(len(self._orderbooks_product))
        self._sync_task = asyncio.create_task(cancelable(self._sync_orderbooks()))
        await self._initial_orderbook_fetched.wait()
        return self

    async def __aexit__(self, exc_type: ExcType, exc: ExcValue, tb: Traceback) -> None:
        await cancel(self._sync_task)

    def get_updated_event(self, exchange: str, symbol: str) -> Event[None]:
        return self._data[exchange][symbol].updated

    def list_asks(self, exchange: str, symbol: str) -> List[Tuple[Decimal, Decimal]]:
        return sorted(self._data[exchange][symbol][Side.BUY].items())

    def list_bids(self, exchange: str, symbol: str) -> List[Tuple[Decimal, Decimal]]:
        return sorted(self._data[exchange][symbol][Side.SELL].items(), reverse=True)

    async def _sync_orderbooks(self) -> None:
        await asyncio.gather(*(self._sync_orderbook(e, s) for e, s in self._orderbooks_product))

    @backoff.on_exception(backoff.expo, (Exception,), max_tries=3)
    async def _sync_orderbook(self, exchange: str, symbol: str) -> None:
        orderbook = self._data[exchange][symbol]
        async for depth in self._stream_depth(exchange, symbol):
            if isinstance(depth, DepthSnapshot):
                orderbook[Side.BUY] = {k: v for k, v in depth.asks}
                orderbook[Side.SELL] = {k: v for k, v in depth.bids}
                orderbook.snapshot_received = True
                self._initial_orderbook_fetched.release()
            elif isinstance(depth, DepthUpdate):
                assert orderbook.snapshot_received
                _update_orderbook_side(orderbook[Side.BUY], depth.asks)
                _update_orderbook_side(orderbook[Side.SELL], depth.bids)
            else:
                raise NotImplementedError(depth)
            orderbook.updated.set()

    async def _stream_depth(self, exchange: str,
                            symbol: str) -> AsyncIterable[Union[DepthSnapshot, DepthUpdate]]:
        exchange_instance = self._exchanges[exchange]

        async with exchange_instance.connect_stream_depth(symbol) as stream:
            if exchange_instance.depth_ws_snapshot:
                async for depth in stream:
                    yield depth
            else:
                snapshot = await exchange_instance.get_depth(symbol)
                yield snapshot

                last_update_id = snapshot.last_id
                is_first_update = True
                async for update in stream:
                    assert isinstance(update, DepthUpdate)

                    if update.last_id <= last_update_id:
                        continue

                    if is_first_update:
                        assert (
                            update.first_id <= last_update_id + 1
                            and update.last_id >= last_update_id + 1
                        )
                        is_first_update = False
                    elif update.first_id != last_update_id + 1:
                        _log.warning(
                            f'orderbook out of sync: {update.first_id=} != {last_update_id=} + 1; '
                            'refetching snapshot'
                        )
                        async for data in self._stream_depth(exchange, symbol):
                            yield data
                        break

                    yield update
                    last_update_id = update.last_id


def _update_orderbook_side(
    orderbook_side: Dict[Decimal, Decimal], values: List[Tuple[Decimal, Decimal]]
) -> None:
    for price, size in values:
        if size > 0:
            orderbook_side[price] = size
        elif price in orderbook_side:
            del orderbook_side[price]
        else:
            # Receiving an event that removes a price level that is not in the local orderbook can
            # happen and is normal for Binance, for example.
            pass


class _OrderbookData(Dict[Side, Dict[Decimal, Decimal]]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.updated: Event[None] = Event(autoclear=True)
        self.snapshot_received = False
