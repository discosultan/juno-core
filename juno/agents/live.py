from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from juno.brokers import Broker
from juno.components import Chandler, Informant, Wallet
from juno.math import floor_multiple
from juno.strategies import new_strategy
from juno.time import MAX_TIME_MS, time_ms
from juno.trading import Trader
from juno.utils import unpack_symbol

from .agent import Agent


class Live(Agent):
    def __init__(
        self, chandler: Chandler, informant: Informant, wallet: Wallet, broker: Broker
    ) -> None:
        super().__init__()
        self.chandler = chandler
        self.informant = informant
        self.wallet = wallet
        self.broker = broker

    async def run(
        self,
        exchange: str,
        symbol: str,
        interval: int,
        strategy_config: Dict[str, Any],
        end: int = MAX_TIME_MS,
        missed_candle_policy: str = 'ignore',
        adjust_start: bool = True,
        trailing_stop: Decimal = Decimal('0.0'),
        get_time_ms: Optional[Callable[[], int]] = None
    ) -> None:
        if not get_time_ms:
            get_time_ms = time_ms

        current = floor_multiple(get_time_ms(), interval)
        end = floor_multiple(end, interval)
        assert end > current

        _, quote_asset = unpack_symbol(symbol)
        quote = self.wallet.get_balance(exchange, quote_asset).available

        _, filters = self.informant.get_fees_filters(exchange, symbol)
        assert quote > filters.price.min

        trader = Trader(
            chandler=self.chandler,
            informant=self.informant,
            exchange=exchange,
            symbol=symbol,
            interval=interval,
            start=current,
            end=end,
            quote=quote,
            new_strategy=lambda: new_strategy(strategy_config),
            broker=self.broker,
            test=False,
            event=self,
            missed_candle_policy=missed_candle_policy,
            adjust_start=adjust_start,
            trailing_stop=trailing_stop,
        )
        self.result = trader.summary
        await trader.run()
