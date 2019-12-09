import asyncio
import logging
import os

from juno import exchanges

EXCHANGE_TYPE = exchanges.Kraken
SYMBOL = 'ada-eur'


async def main():
    name = EXCHANGE_TYPE.__name__.upper()
    async with EXCHANGE_TYPE(
        os.environ[f'JUNO__{name}__API_KEY'], os.environ[f'JUNO__{name}__SECRET_KEY']
    ) as client:
        async with client.connect_stream_depth(SYMBOL) as stream:
            async for val in stream:
                logging.info(val)


asyncio.run(main())