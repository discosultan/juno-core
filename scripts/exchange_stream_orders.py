import asyncio
import logging

from juno import exchanges
from juno.config import from_env, init_instance

EXCHANGE_TYPE = exchanges.Binance
SYMBOL = 'iota-btc'


async def main() -> None:
    async with init_instance(EXCHANGE_TYPE, from_env()) as client:
        async with client.connect_stream_orders(symbol=SYMBOL) as stream:
            async for val in stream:
                logging.info(val)


asyncio.run(main())
