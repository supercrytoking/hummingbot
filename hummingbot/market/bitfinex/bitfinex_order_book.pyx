import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy.engine import RowProxy
import ujson

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bitfinex.bitfinex_order_book_message import \
    BitfinexOrderBookMessage

_logger = None


cdef class BitfinexOrderBook(OrderBook):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _logger

        if _logger is None:
            _logger = logging.getLogger(__name__)

        return _logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, Any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)

        msg.update(type=str(OrderBookMessageType.SNAPSHOT.value))
        return BitfinexOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        if "time" in msg:
            msg_time = pd.Timestamp(msg["time"]).timestamp()

        return BitfinexOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp or msg_time)

    @classmethod
    def snapshot_message_from_db(cls,
                                 record: RowProxy,
                                 metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = record.json if type(record.json)==dict else ujson.loads(record.json)
        return BitfinexOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=record.timestamp * 1e-3
        )

    @classmethod
    def diff_message_from_db(cls,
                             record: RowProxy,
                             metadata: Optional[Dict] = None) -> OrderBookMessage:
        return BitfinexOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=record.json,
            timestamp=record.timestamp * 1e-3
        )

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, Any], metadata: Optional[Dict] = None):
        if metadata:
            msg.update(metadata)

        timestamp = msg["mts"]
        trade_type = TradeType.SELL if int(msg["amount"]) < 0 else TradeType.BUY
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["symbol"],
                "trade_type": float(trade_type.value),
                "trade_id": msg["id"],
                "update_id": timestamp,
                "price": msg["price"],
                "amount": abs(msg["amount"]),
            },
            timestamp= timestamp * 1e-3
        )

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError("Bitfinex order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError("Bitfinex order book needs to retain individual order data.")
