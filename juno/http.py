from contextlib import asynccontextmanager
import logging

import aiohttp


_aiohttp_log = logging.getLogger('aiohttp.client')


# Adds logging to aiohttp client session.
# https://stackoverflow.com/a/45590516/1466456
# Note that aiohttp client session is not meant to be extended.
# https://github.com/aio-libs/aiohttp/issues/3185
class ClientSession:

    def __init__(self, *args, **kwargs):
        self._raise_for_status = kwargs.pop('raise_for_status', None)
        self._session = aiohttp.ClientSession(*args, **kwargs)

    async def __aenter__(self):
        await self._session.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._session.__aexit__(exc_type, exc, tb)

    def request(self, method, url, **kwargs):
        return _RequestContextManagerWrapper(
            self._session.request(method, url, **kwargs),
            self._raise_for_status,
            method,
            url,
            kwargs)

    @asynccontextmanager
    async def ws_connect(self, url, **kwargs):
        _aiohttp_log.info(f'WS {url}')
        _aiohttp_log.debug(kwargs)
        async with self._session.ws_connect(url, **kwargs) as ws:
            yield _ClientWebSocketResponseWrapper(ws)


class _RequestContextManagerWrapper:

    def __init__(self, rcm, raise_for_status, method, url, kwargs):
        self._rcm = rcm
        self._raise_for_status = raise_for_status
        self._method = method
        self._url = url
        self._kwargs = kwargs

    async def __aenter__(self):
        _aiohttp_log.info(f'{self._method} {self._url}')
        _aiohttp_log.debug(self._kwargs)
        res = await self._rcm.__aenter__()
        _aiohttp_log.info(f'{res.status} {res.reason}')
        if res.status >= 400:
            _aiohttp_log.error(await res.text())
            if self._raise_for_status:
                res.raise_for_status()
        else:
            _aiohttp_log.debug(await res.text())
        return res

    async def __aexit__(self, exc_type, exc, tb):
        await self._rcm.__aexit__(exc_type, exc, tb)


class _ClientWebSocketResponseWrapper:

    def __init__(self, client_ws_response):
        self._client_ws_response = client_ws_response

    def __aiter__(self):
        return self

    async def __anext__(self):
        msg = await self._client_ws_response.__anext__()
        _aiohttp_log.debug(msg)
        return msg

    def send_json(self, data):
        _aiohttp_log.debug(data)
        return self._client_ws_response.send_json(data)
