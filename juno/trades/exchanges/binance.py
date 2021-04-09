from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any, AsyncIterable, AsyncIterator

from juno.exchanges.binance import Session
from juno.time import HOUR_MS, HOUR_SEC
from juno.trades import Trade
from juno.trades.exchanges import Exchange


class Binance(Exchange):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def stream_historical_trades(
        self, symbol: str, start: int, end: int
    ) -> AsyncIterable[Trade]:
        # Aggregated trades. This means trades executed at the same time, same price and as part of
        # the same order will be aggregated by summing their size.
        batch_start = start
        payload: dict[str, Any] = {
            'symbol': _to_http_symbol(symbol),
        }
        while True:
            batch_end = batch_start + HOUR_MS
            payload['startTime'] = batch_start
            payload['endTime'] = min(batch_end, end) - 1  # Inclusive.

            time = None

            content = await self._session.request_json('GET', '/api/v3/aggTrades', data=payload)
            for t in content:
                time = t['T']
                assert time < end
                yield Trade(
                    id=t['a'],
                    time=time,
                    price=Decimal(t['p']),
                    size=Decimal(t['q']),
                )
            batch_start = time + 1 if time is not None else batch_end
            if batch_start >= end:
                break

    @asynccontextmanager
    async def connect_stream_trades(self, symbol: str) -> AsyncIterator[AsyncIterable[Trade]]:
        async def inner(ws: AsyncIterable[Any]) -> AsyncIterable[Trade]:
            async for data in ws:
                yield Trade(
                    id=data['a'],
                    time=data['T'],
                    price=Decimal(data['p']),
                    size=Decimal(data['q']),
                )

        # https://github.com/binance-exchange/binance-official-api-docs/blob/master/web-socket-streams.md#trade-streams
        async with self._session.connect_refreshing_stream(
            url=f'/ws/{_to_ws_symbol(symbol)}@trade', interval=12 * HOUR_SEC, name='trade',
            raise_on_disconnect=True
        ) as ws:
            yield inner(ws)


def _to_http_symbol(symbol: str) -> str:
    return symbol.replace('-', '').upper()


def _to_ws_symbol(symbol: str) -> str:
    return symbol.replace('-', '')
