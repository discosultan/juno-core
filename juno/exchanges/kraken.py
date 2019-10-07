from __future__ import annotations

from typing import Any, Optional

import simplejson as json

from juno import Fees, Filters, Symbols
from juno.http import ClientSession
from juno.typing import ExcType, ExcValue, Traceback

from .exchange import Exchange

_BASE_URL = 'https://api.kraken.com'


class Kraken(Exchange):
    def __init__(self, api_key: str, secret_key: str) -> None:
        super().__init__()
        self._api_key = api_key
        self._secret_key_bytes = secret_key.encode('utf-8')

    async def __aenter__(self) -> Kraken:
        self._session = ClientSession(raise_for_status=True)
        await self._session.__aenter__()
        return self

    async def __aexit__(self, exc_type: ExcType, exc: ExcValue, tb: Traceback) -> None:
        await self._session.__aexit__(exc_type, exc, tb)

    async def map_symbols(self) -> Symbols:
        res = await self._request('GET', '/0/public/AssetPairs')
        fees, filters = {}, {}
        for val in res['result'].values():
            name = _from_wsname(val['wsname'])
            # TODO: Take into account different fee levels. Currently only worst level.
            taker_fee = val['fees'][0][1]
            maker_fees = val.get('fees_maker')
            fees[name] = Fees(maker=maker_fees[0][1] if maker_fees else taker_fee, taker=taker_fee)
            filters[name] = Filters(
                base_precision=val['lot_decimals'],
                quote_precision=val['pair_decimals'],
            )
        return Symbols(fees=fees, filters=filters)

    # def _query(self, urlpath, data, headers=None, timeout=None):
    #     """ Low-level query handling.
    #     .. note::
    #        Use :py:meth:`query_private` or :py:meth:`query_public`
    #        unless you have a good reason not to.
    #     :param urlpath: API URL path sans host
    #     :type urlpath: str
    #     :param data: API request parameters
    #     :type data: dict
    #     :param headers: (optional) HTTPS headers
    #     :type headers: dict
    #     :param timeout: (optional) if not ``None``, a :py:exc:`requests.HTTPError`
    #                     will be thrown after ``timeout`` seconds if a response
    #                     has not been received
    #     :type timeout: int or float
    #     :returns: :py:meth:`requests.Response.json`-deserialised Python object
    #     :raises: :py:exc:`requests.HTTPError`: if response status not successful
    #     """
    #     if data is None:
    #         data = {}
    #     if headers is None:
    #         headers = {}

    #     url = self.uri + urlpath

    #     self.response = self.session.post(url, data = data, headers = headers,
    #                                       timeout = timeout)

    #     if self.response.status_code not in (200, 201, 202):
    #         self.response.raise_for_status()

    #     return self.response.json(**self._json_options)

    # async def _request_public(self, method: str, url: str, data: Optional[Any] = None):
    #     data = data or {}

    async def _request(self, method: str, url: str, data: Optional[Any] = None):
        data = data or {}
        async with self._session.request(method=method, url=_BASE_URL + url) as res:
            return await res.json(loads=json.loads)

    # def query_public(self, method, data=None, timeout=None):
    #     """ Performs an API query that does not require a valid key/secret pair.
    #     :param method: API method name
    #     :type method: str
    #     :param data: (optional) API request parameters
    #     :type data: dict
    #     :param timeout: (optional) if not ``None``, a :py:exc:`requests.HTTPError`
    #                     will be thrown after ``timeout`` seconds if a response
    #                     has not been received
    #     :type timeout: int or float
    #     :returns: :py:meth:`requests.Response.json`-deserialised Python object
    #     """
    #     if data is None:
    #         data = {}

    #     urlpath = '/' + self.apiversion + '/public/' + method

    #     return self._query(urlpath, data, timeout = timeout)

    # def query_private(self, method, data=None, timeout=None):
    #     """ Performs an API query that requires a valid key/secret pair.
    #     :param method: API method name
    #     :type method: str
    #     :param data: (optional) API request parameters
    #     :type data: dict
    #     :param timeout: (optional) if not ``None``, a :py:exc:`requests.HTTPError`
    #                     will be thrown after ``timeout`` seconds if a response
    #                     has not been received
    #     :type timeout: int or float
    #     :returns: :py:meth:`requests.Response.json`-deserialised Python object
    #     """
    #     if data is None:
    #         data = {}

    #     if not self.key or not self.secret:
    #         raise Exception('Either key or secret is not set! (Use `load_key()`.')

    #     data['nonce'] = self._nonce()

    #     urlpath = '/' + self.apiversion + '/private/' + method

    #     headers = {
    #         'API-Key': self.key,
    #         'API-Sign': self._sign(data, urlpath)
    #     }

    #     return self._query(urlpath, data, headers, timeout = timeout)

    # def _nonce(self):
    #     """ Nonce counter.
    #     :returns: an always-increasing unsigned integer (up to 64 bits wide)
    #     """
    #     return int(1000*time.time())

    # def _sign(self, data, urlpath):
    #     """ Sign request data according to Kraken's scheme.
    #     :param data: API request parameters
    #     :type data: dict
    #     :param urlpath: API URL path sans host
    #     :type urlpath: str
    #     :returns: signature digest
    #     """
    #     postdata = urllib.parse.urlencode(data)

    #     # Unicode-objects must be encoded before hashing
    #     encoded = (str(data['nonce']) + postdata).encode()
    #     message = urlpath.encode() + hashlib.sha256(encoded).digest()

    #     signature = hmac.new(base64.b64decode(self.secret),
    #                          message, hashlib.sha512)
    #     sigdigest = base64.b64encode(signature.digest())

    #     return sigdigest.decode()


def _from_wsname(wsname: str) -> str:
    return '-'.join(wsname.split('/')).lower()
