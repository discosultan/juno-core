from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Dict, List

import aiohttp
import pytest

import juno
from juno import (
    Balance, Candle, DepthSnapshot, DepthUpdate, ExchangeInfo, OrderType, Side, Ticker, Trade
)
from juno.config import init_instance
from juno.exchanges import Binance, Coinbase, Exchange, Kraken
from juno.time import HOUR_MS, MIN_MS, strptimestamp, time_ms
from juno.typing import types_match
from juno.utils import list_concretes_from_module

exchange_types = list_concretes_from_module(juno.exchanges, Exchange)
exchanges = [pytest.lazy_fixture(e.__name__.lower()) for e in exchange_types]
exchange_ids = [e.__name__ for e in exchange_types]


# We use a session-scoped loop for shared rate-limiting.
@pytest.fixture(scope='session')
def loop():
    with aiohttp.test_utils.loop_context() as loop:
        yield loop


@pytest.fixture(scope='session')
async def binance(loop, config):
    async with try_init_exchange(Binance, config) as exchange:
        yield exchange


@pytest.fixture(scope='session')
async def coinbase(loop, config):
    async with try_init_exchange(Coinbase, config) as exchange:
        yield exchange


@pytest.fixture(scope='session')
async def kraken(loop, config):
    async with try_init_exchange(Kraken, config) as exchange:
        yield exchange


@pytest.mark.exchange
@pytest.mark.manual
@pytest.mark.parametrize('exchange', exchanges, ids=exchange_ids)
async def test_get_exchange_info(loop, request, exchange):
    skip_not_configured(request, exchange)

    res = await exchange.get_exchange_info()

    assert len(res.fees) > 0
    first_fees = next(iter(res.fees.values()))
    assert 0 <= first_fees.taker <= Decimal('0.1')
    assert 0 <= first_fees.maker <= Decimal('0.1')
    assert -4 <= first_fees.taker.as_tuple().exponent <= -1
    assert -4 <= first_fees.maker.as_tuple().exponent <= -1
    if '__all__' not in res.fees:
        assert res.fees['eth-btc']

    assert len(res.filters) > 0
    if '__all__' not in res.filters:
        assert res.filters['eth-btc']

    assert types_match(res, ExchangeInfo)


@pytest.mark.exchange
@pytest.mark.manual
@pytest.mark.parametrize('exchange', exchanges, ids=exchange_ids)
async def test_list_24hr_tickers(loop, request, exchange):
    skip_not_configured(request, exchange)
    skip_no_capability(exchange.can_list_24hr_tickers)

    # Note, this is an expensive call!
    res = await exchange.list_24hr_tickers()

    assert len(res) > 0
    assert types_match(res, List[Ticker])


@pytest.mark.exchange
@pytest.mark.manual
@pytest.mark.parametrize('exchange', exchanges, ids=exchange_ids)
async def test_get_balances(loop, request, exchange):
    skip_not_configured(request, exchange)

    res = await exchange.get_balances()

    assert types_match(res, Dict[str, Balance])


@pytest.mark.exchange
@pytest.mark.manual
@pytest.mark.parametrize('exchange', exchanges, ids=exchange_ids)
async def test_stream_historical_candles(loop, request, exchange):
    skip_not_configured(request, exchange)
    skip_no_capability(exchange.can_stream_historical_candles)

    start = strptimestamp('2018-01-01')

    stream = exchange.stream_historical_candles(
        symbol='eth-btc', interval=HOUR_MS, start=start, end=start + HOUR_MS
    )
    candle = await stream.__anext__()

    assert types_match(candle, Candle)
    assert candle.time == start

    with pytest.raises(StopAsyncIteration):
        await stream.__anext__()


@pytest.mark.exchange
@pytest.mark.manual
@pytest.mark.parametrize('exchange', exchanges, ids=exchange_ids)
async def test_connect_stream_candles(loop, request, exchange):
    skip_not_configured(request, exchange)
    skip_no_capability(exchange.can_stream_candles)

    async with exchange.connect_stream_candles(symbol='eth-btc', interval=HOUR_MS) as stream:
        candle = await stream.__anext__()
        await stream.aclose()

    assert types_match(candle, Candle)


@pytest.mark.exchange
@pytest.mark.manual
@pytest.mark.parametrize('exchange', exchanges, ids=exchange_ids)
async def test_get_depth(loop, request, exchange):
    skip_not_configured(request, exchange)
    skip_no_capability(not exchange.can_stream_depth_snapshot)

    res = await exchange.get_depth('eth-btc')

    assert types_match(res, DepthSnapshot)


@pytest.mark.exchange
@pytest.mark.manual
@pytest.mark.parametrize('exchange', exchanges, ids=exchange_ids)
async def test_connect_stream_depth(loop, request, exchange):
    skip_not_configured(request, exchange)

    async with exchange.connect_stream_depth('eth-btc') as stream:
        res = await stream.__anext__()
        await stream.aclose()

    expected_type = DepthSnapshot if exchange.can_stream_depth_snapshot else DepthUpdate

    assert types_match(res, expected_type)


@pytest.mark.exchange
@pytest.mark.manual
@pytest.mark.parametrize('exchange', exchanges, ids=exchange_ids)
async def test_place_order(loop, request, exchange):
    skip_not_configured(request, exchange)
    skip_exchange(exchange, Coinbase, Kraken)

    await exchange.place_order(
        symbol='eth-btc', side=Side.BUY, type_=OrderType.MARKET, size=Decimal('1.0'), test=True
    )


@pytest.mark.exchange
@pytest.mark.manual
@pytest.mark.parametrize('exchange', exchanges, ids=exchange_ids)
async def test_stream_historical_trades(loop, request, exchange):
    skip_not_configured(request, exchange)

    # Coinbase can only stream from most recent, hence we use current time.
    if isinstance(exchange, Coinbase):
        end = time_ms()
        start = end - 5 * MIN_MS
    else:
        start = strptimestamp('2018-01-01')
        end = start + HOUR_MS

    stream = exchange.stream_historical_trades(symbol='eth-btc', start=start, end=end)
    trade = await stream.__anext__()
    await stream.aclose()

    assert types_match(trade, Trade)
    assert trade.time >= start


@pytest.mark.exchange
@pytest.mark.manual
@pytest.mark.parametrize('exchange', exchanges, ids=exchange_ids)
async def test_connect_stream_trades(loop, request, exchange):
    skip_not_configured(request, exchange)

    # FIAT pairs seem to be more active where supported.
    symbol = 'eth-btc' if isinstance(exchange, Binance) else 'eth-eur'

    async with exchange.connect_stream_trades(symbol=symbol) as stream:
        trade = await stream.__anext__()
        await stream.aclose()

    assert types_match(trade, Trade)


def skip_not_configured(request, exchange):
    markers = ['exchange', 'manual']
    if request.config.option.markexpr not in markers:
        pytest.skip(f'Specify {"" or "".join(markers)} marker to run!')
    if not exchange:
        pytest.skip('Exchange params not configured')


def skip_exchange(exchange, *skip_exchange_types):
    type_ = type(exchange)
    if type_ in skip_exchange_types:
        pytest.skip(f'Not implemented for {type_.__name__.lower()}')


def skip_no_capability(has_capability):
    if not has_capability:
        pytest.skip('Does not have the capability')


@asynccontextmanager
async def try_init_exchange(type_, config):
    try:
        async with init_instance(type_, config) as exchange:
            yield exchange
    except TypeError:
        yield None
