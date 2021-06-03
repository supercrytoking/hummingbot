#!/usr/bin/env python
from typing import (
    NamedTuple,
    List
)
from decimal import Decimal
from hummingbot.core.event.events import OrderType
from dataclasses import dataclass

import time

ORDER_PROPOSAL_ACTION_CREATE_ORDERS = 1
ORDER_PROPOSAL_ACTION_CANCEL_ORDERS = 1 << 1

NaN = float("nan")


class OrdersProposal(NamedTuple):
    actions: int
    buy_order_type: OrderType
    buy_order_prices: List[Decimal]
    buy_order_sizes: List[Decimal]
    sell_order_type: OrderType
    sell_order_prices: List[Decimal]
    sell_order_sizes: List[Decimal]
    cancel_order_ids: List[str]


class PricingProposal(NamedTuple):
    buy_order_prices: List[Decimal]
    sell_order_prices: List[Decimal]


class SizingProposal(NamedTuple):
    buy_order_sizes: List[Decimal]
    sell_order_sizes: List[Decimal]


class PriceSize:
    def __init__(self, price: Decimal, size: Decimal):
        self.price: Decimal = price
        self.size: Decimal = size

    def __repr__(self):
        return f"[ p: {self.price} s: {self.size} ]"


class Proposal:
    def __init__(self, buys: List[PriceSize], sells: List[PriceSize]):
        self.buys: List[PriceSize] = buys
        self.sells: List[PriceSize] = sells

    def __repr__(self):
        return f"{len(self.buys)} buys: {', '.join([str(o) for o in self.buys])} " \
               f"{len(self.sells)} sells: {', '.join([str(o) for o in self.sells])}"


@dataclass
class HangingOrder:
    order_id: str
    trading_pair: str
    is_buy: bool
    price: Decimal
    amount: Decimal

    @property
    def base_asset(self):
        return self.trading_pair.split('-')[0]

    @property
    def quote_asset(self):
        return self.trading_pair.split('-')[1]

    @property
    def creation_timestamp(self):
        if "//" not in self.order_id:
            return int(self.order_id[-16:]) / 1e6

    @property
    def age(self):
        if self.creation_timestamp:
            return int(time.time()) - self.creation_timestamp
        return 0

    def distance_to_price(self, price: Decimal):
        return abs(self.price - price)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash((self.trading_pair, self.price, self.amount, self.is_buy))
