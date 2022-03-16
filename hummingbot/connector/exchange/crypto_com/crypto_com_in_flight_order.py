import asyncio
from decimal import Decimal
from typing import (
    Any,
    Dict,
    Optional,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.connector.in_flight_order_base import InFlightOrderBase


class CryptoComInFlightOrder(InFlightOrderBase):
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 price: Decimal,
                 amount: Decimal,
                 creation_timestamp: float,
                 initial_state: str = "OPEN"):
        super().__init__(
            client_order_id,
            exchange_order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            creation_timestamp,
            initial_state,
        )
        self.trade_id_set = set()
        self.cancelled_event = asyncio.Event()

    @property
    def is_done(self) -> bool:
        return self.last_state in {"FILLED", "CANCELED", "REJECTED", "EXPIRED"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"REJECTED"}

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"CANCELED", "EXPIRED"}

    def update_with_trade_update(self, trade_update: Dict[str, Any]) -> bool:
        """
        Updates the in flight order with trade update (from private/get-order-detail end point)
        return: True if the order gets updated otherwise False
        """
        trade_id = trade_update["trade_id"]
        # trade_update["orderId"] is type int
        if str(trade_update["order_id"]) != self.exchange_order_id or trade_id in self.trade_id_set:
            # trade already recorded
            return False
        self.trade_id_set.add(trade_id)
        self.executed_amount_base += Decimal(str(trade_update["traded_quantity"]))
        self.fee_paid += Decimal(str(trade_update["fee"]))
        self.executed_amount_quote += (Decimal(str(trade_update["traded_price"])) *
                                       Decimal(str(trade_update["traded_quantity"])))
        if not self.fee_asset:
            self.fee_asset = trade_update["fee_currency"]
        return True
