#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from typing import List
from decimal import Decimal
import logging; logging.basicConfig(level=logging.ERROR)
import pandas as pd
import unittest

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import QuantizationParams
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderBookTradeEvent,
    TradeType
)
from hummingbot.strategy.pure_market_making.pure_market_making import PureMarketMakingStrategy
from hummingbot.strategy.pure_market_making.order_book_asset_price_delegate import OrderBookAssetPriceDelegate
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow


# Update the orderbook so that the top bids and asks are lower than actual for a wider bid ask spread
# this basially removes the orderbook entries above top bid and below top ask
def simulate_order_book_widening(order_book: OrderBook, top_bid: float, top_ask: float):
    bid_diffs: List[OrderBookRow] = []
    ask_diffs: List[OrderBookRow] = []
    update_id: int = order_book.last_diff_uid + 1
    for row in order_book.bid_entries():
        if row.price > top_bid:
            bid_diffs.append(OrderBookRow(row.price, 0, update_id))
        else:
            break
    for row in order_book.ask_entries():
        if row.price < top_ask:
            ask_diffs.append(OrderBookRow(row.price, 0, update_id))
        else:
            break
    order_book.apply_diffs(bid_diffs, ask_diffs, update_id)


class PureMMTakeIfCrossUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    trading_pair = "HBOT-ETH"
    base_asset = trading_pair.split("-")[0]
    quote_asset = trading_pair.split("-")[1]

    def setUp(self):
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.market: BacktestMarket = BacktestMarket()
        self.book_data: MockOrderBookLoader = MockOrderBookLoader(self.trading_pair, self.base_asset, self.quote_asset)
        self.mid_price = 100
        self.bid_spread = 0.01
        self.ask_spread = 0.01
        self.order_refresh_time = 30
        self.book_data.set_balanced_order_book(mid_price=self.mid_price,
                                               min_price=1,
                                               max_price=200,
                                               price_step_size=1,
                                               volume_step_size=10)
        self.market.add_data(self.book_data)
        self.market.set_balance("HBOT", 500)
        self.market.set_balance("ETH", 5000)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair, 6, 6, 6, 6
            )
        )
        self.market_info = MarketTradingPairTuple(self.market, self.trading_pair,
                                                  self.base_asset, self.quote_asset)
        self.clock.add_iterator(self.market)
        self.order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.market.add_listener(MarketEvent.OrderFilled, self.order_fill_logger)
        self.market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)

        self.ext_market: BacktestMarket = BacktestMarket()
        self.ext_data: MockOrderBookLoader = MockOrderBookLoader(self.trading_pair, self.base_asset, self.quote_asset)
        self.ext_market_info: MarketTradingPairTuple = MarketTradingPairTuple(
            self.ext_market, self.trading_pair, self.base_asset, self.quote_asset
        )
        self.ext_data.set_balanced_order_book(mid_price=100, min_price=1, max_price=400, price_step_size=1,
                                              volume_step_size=100)
        self.ext_market.add_data(self.ext_data)
        self.order_book_asset_del = OrderBookAssetPriceDelegate(self.ext_market, self.trading_pair)

        self.one_level_strategy = PureMarketMakingStrategy(
            self.market_info,
            bid_spread=Decimal("0.01"),
            ask_spread=Decimal("0.01"),
            order_amount=Decimal("1"),
            order_refresh_time=3.0,
            filled_order_delay=3.0,
            order_refresh_tolerance_pct=-1,
            minimum_spread=-1,
            asset_price_delegate=self.order_book_asset_del,
            take_if_crossed=True
        )

    def simulate_maker_market_trade(self, is_buy: bool, quantity: Decimal, price: Decimal):
        order_book = self.market.get_order_book(self.trading_pair)
        trade_event = OrderBookTradeEvent(
            self.trading_pair,
            self.clock.current_timestamp,
            TradeType.BUY if is_buy else TradeType.SELL,
            price,
            quantity
        )
        order_book.apply_trade(trade_event)

    def test_strategy_take_if_crossed_bid_order(self):
        simulate_order_book_widening(self.ext_market.get_order_book(self.trading_pair), 120.0, 130.0)
        self.strategy = self.one_level_strategy
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(0, len(self.order_fill_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        self.clock.backtest_til(
            self.start_timestamp + 2 * self.clock_tick_size
        )
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(0, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        self.clock.backtest_til(
            self.start_timestamp + 7 * self.clock_tick_size
        )
        self.assertEqual(2, len(self.order_fill_logger.event_log))
        self.assertEqual(0, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        self.clock.backtest_til(
            self.start_timestamp + 10 * self.clock_tick_size
        )
        self.assertEqual(3, len(self.order_fill_logger.event_log))
        self.assertEqual(0, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))
        self.order_fill_logger.clear()

    def test_strategy_take_if_crossed_ask_order(self):
        simulate_order_book_widening(self.ext_market.get_order_book(self.trading_pair), 80.0, 90.0)
        self.strategy = self.one_level_strategy
        self.clock.add_iterator(self.strategy)

        self.clock.backtest_til(self.start_timestamp + self.clock_tick_size)
        self.assertEqual(0, len(self.order_fill_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(1, len(self.strategy.active_sells))

        self.clock.backtest_til(
            self.start_timestamp + 2 * self.clock_tick_size
        )
        self.assertEqual(1, len(self.order_fill_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(0, len(self.strategy.active_sells))

        self.clock.backtest_til(
            self.start_timestamp + 6 * self.clock_tick_size
        )
        self.assertEqual(2, len(self.order_fill_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(0, len(self.strategy.active_sells))

        self.clock.backtest_til(
            self.start_timestamp + 10 * self.clock_tick_size
        )
        self.assertEqual(3, len(self.order_fill_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_buys))
        self.assertEqual(0, len(self.strategy.active_sells))
        self.order_fill_logger.clear()
