import argparse
import asyncio
import logging

from juno.exchanges import Exchange

parser = argparse.ArgumentParser()
parser.add_argument('asset', nargs='?')
parser.add_argument('-e', '--exchange', default='binance')
args = parser.parse_args()


async def main() -> None:
    async with Exchange.from_env(args.exchange) as exchange:
        deposit_address = await exchange.get_deposit_address(args.asset)
    logging.info(f'{args.asset}: {deposit_address}')


asyncio.run(main())
