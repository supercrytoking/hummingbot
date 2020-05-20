#!/usr/bin/env python

from typing import (
    Dict,
    List,
    Optional,
)

from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)


class BitcoinComOrderBookMessage(OrderBookMessage):
    def __new__(
        cls,
        message_type: OrderBookMessageType,
        content: Dict[str, any],
        timestamp: Optional[float] = None,
        *args,
        **kwargs,
    ):
        if timestamp is None:
            if message_type is OrderBookMessageType.SNAPSHOT:
                raise ValueError("timestamp must not be None when initializing snapshot messages.")
            timestamp = content["timestamp"]

        return super(BitcoinComOrderBookMessage, cls).__new__(
            cls, message_type, content, timestamp=timestamp, *args, **kwargs
        )

    @property
    def update_id(self) -> int:
        if self.type in [OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT]:
            # TODO: switch into using this
            # return int(self.content["sequence"])
            return int(self.timestamp * 1e3)
        else:
            return -1

    @property
    def trade_id(self) -> int:
        if self.type is OrderBookMessageType.TRADE:
            return int(self.content["id"])
        return -1

    @property
    def trading_pair(self) -> str:
        if "trading_pair" in self.content:
            return self.content["trading_pair"]
        elif "symbol" in self.content:
            return self.content["symbol"]

    @property
    def asks(self) -> List[OrderBookRow]:
        return [
            OrderBookRow(float(price), float(size), self.update_id) for price, size, *trash in self.content["ask"]
        ]

    @property
    def bids(self) -> List[OrderBookRow]:
        return [
            OrderBookRow(float(price), float(size), self.update_id) for price, size, *trash in self.content["bid"]
        ]

    def __eq__(self, other) -> bool:
        return self.type == other.type and self.timestamp == other.timestamp

    def __lt__(self, other) -> bool:
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        else:
            """
            If timestamp is the same, the ordering is snapshot < diff < trade
            """
            return self.type.value < other.type.value
