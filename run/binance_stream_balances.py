import asyncio
import logging
import os

from juno.exchanges import Binance


async def main():
    async with Binance(
        os.environ['JUNO__BINANCE__API_KEY'], os.environ['JUNO__BINANCE__SECRET_KEY']
    ) as client:
        async with client.connect_stream_balances() as stream:
            async for val in stream:
                logging.info(val)


logging.basicConfig(level='DEBUG')
asyncio.run(main())
