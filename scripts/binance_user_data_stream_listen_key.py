import asyncio
import logging
import os

from juno import JunoException
from juno.exchanges import Binance

JunoException()


async def main() -> None:
    async with Binance(
        os.environ[f'JUNO__BINANCE__API_KEY'], os.environ[f'JUNO__BINANCE__SECRET_KEY']
    ) as client:
        listen_key1 = (await client._user_data_stream._create_listen_key()).data['listenKey']
        listen_key2 = (await client._user_data_stream._create_listen_key()).data['listenKey']
        await client._user_data_stream._update_listen_key(listen_key2)
        await client._user_data_stream._update_listen_key(listen_key1)
        # CAREFUL!! This may delete a listen key to active Juno instance if it's tied to the same
        # account.
        # await client._user_data_stream._delete_listen_key(listen_key2)
        # try:
        #     await client._user_data_stream._update_listen_key(listen_key1)
        # except JunoException:
        #     pass
        # await client._user_data_stream._delete_listen_key(listen_key1)
    logging.info('done')


asyncio.run(main())