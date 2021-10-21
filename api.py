import logging
import os
from typing import AsyncIterator

import aiohttp_cors
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
        fill_missing_with_last=query.get("fill_missing_with_last") == "true",
    )

    # return web.json_response(type_to_raw(result), dumps=json.dumps)
    # TODO: Remove the candle closed attribute. Then we can remove the mapping below.
    return web.json_response(
        [[c.time, c.open, c.high, c.low, c.close, c.volume] for c in result], dumps=json.dumps
    )


@routes.get("/candle_intervals")
async def candle_intervals(request: web.Request) -> web.Response:
    chandler: Chandler = request.app["chandler"]

    result = chandler.list_candle_intervals(
        exchange=request.query["exchange"],
    )

    return web.json_response(type_to_raw(result), dumps=json.dumps)


logging.basicConfig(
    handlers=create_handlers("color", ["stdout"], "api_logs"),
    level=logging.getLevelName("INFO"),
)

app = web.Application()
app.cleanup_ctx.append(juno)
app.add_routes(routes)

cors = aiohttp_cors.setup(
    app,
    defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    },
)
for route in app.router.routes():
    cors.add(route)

web.run_app(app, port=3030)
