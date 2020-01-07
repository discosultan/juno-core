import asyncio
import logging

from juno import exchanges
from juno.config import from_env, init_instance

EXCHANGE_TYPE = exchanges.Binance


async def main():
    async with init_instance(EXCHANGE_TYPE, from_env()) as client:
        balances = await client.get_balances()
        logging.info(balances)


asyncio.run(main())
