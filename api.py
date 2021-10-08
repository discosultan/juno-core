import logging
import os
from typing import AsyncIterator

from aiohttp import web

import juno.json as json
from juno.components import Chandler
from juno.exchanges import Binance
from juno.logging import create_handlers
from juno.storages import SQLite
from juno.typing import type_to_raw


async def juno(app: web.Application) -> AsyncIterator[None]:
    exchange = Binance(
        api_key=os.environ["JUNO__BINANCE__API_KEY"],
        secret_key=os.environ["JUNO__BINANCE__SECRET_KEY"],
    )
    storage = SQLite()
    chandler = Chandler(storage=storage, exchanges=[exchange])
    async with exchange, storage, chandler:
        app["chandler"] = chandler
        yield


routes = web.RouteTableDef()


@routes.get("/")
async def hello(request: web.Request) -> web.Response:
    return web.Response(text="Hello, world")


@routes.get("/candles")
async def candles(request: web.Request) -> web.Response:
    chandler: Chandler = request.app["chandler"]
    query = request.query

    result = await chandler.list_candles(
        exchange=query["exchange"],
        symbol=query["symbol"],
        interval=int(query["interval"]),
        start=int(query["start"]),
        end=int(query["end"]),
    )

    return web.json_response(type_to_raw(result), dumps=json.dumps)


logging.basicConfig(
    handlers=create_handlers("color", ["stdout"], "api_logs"),
    level=logging.getLevelName("INFO"),
)

app = web.Application()
app.cleanup_ctx.append(juno)
app.add_routes(routes)

web.run_app(app, port=4040)
