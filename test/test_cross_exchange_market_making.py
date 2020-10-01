#!/usr/bin/env python

from os.path import join, realpath
import sys
import pandas as pd
from typing import List
import unittest
from hummingsim.backtest.backtest_market import BacktestMarket
from hummingsim.backtest.market import (
    AssetType,
    Market,
    MarketConfig,
    QuantizationParams
)
from hummingsim.backtest.mock_order_book_loader import MockOrderBookLoader
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    OrderBookTradeEvent,
    TradeType,
    OrderType,
    OrderFilledEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    TradeFee,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
)
from math import floor, ceil
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.cross_exchange_market_making import CrossExchangeMarketMakingStrategy
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_pair import CrossExchangeMarketPair
from nose.plugins.attrib import attr

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from decimal import Decimal
import logging

sys.path.insert(0, realpath(join(__file__, "../../")))


logging.basicConfig(level=logging.ERROR)


@attr("stable")
class HedgedMarketMakingUnitTest(unittest.TestCase):
    start: pd.Timestamp = pd.Timestamp("2019-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2019-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    maker_trading_pairs: List[str] = ["COINALPHA-WETH", "COINALPHA", "WETH"]
    taker_trading_pairs: List[str] = ["coinalpha/eth", "COINALPHA", "ETH"]

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, 1.0, self.start_timestamp, self.end_timestamp)
        self.min_profitbality = Decimal("0.005")
        self.maker_market: BacktestMarket = BacktestMarket()
        self.taker_market: BacktestMarket = BacktestMarket()
        self.maker_data: MockOrderBookLoader = MockOrderBookLoader(*self.maker_trading_pairs)
        self.taker_data: MockOrderBookLoader = MockOrderBookLoader(*self.taker_trading_pairs)
        self.maker_data.set_balanced_order_book(1.0, 0.5, 1.5, 0.01, 10)
        self.taker_data.set_balanced_order_book(1.0, 0.5, 1.5, 0.001, 4)
        self.maker_market.add_data(self.maker_data)
        self.taker_market.add_data(self.taker_data)
        self.maker_market.set_balance("COINALPHA", 5)
        self.maker_market.set_balance("WETH", 5)
        self.maker_market.set_balance("QETH", 5)
        self.taker_market.set_balance("COINALPHA", 5)
        self.taker_market.set_balance("ETH", 5)
        self.maker_market.set_quantization_param(QuantizationParams(self.maker_trading_pairs[0], 5, 5, 5, 5))
        self.taker_market.set_quantization_param(QuantizationParams(self.taker_trading_pairs[0], 5, 5, 5, 5))

        self.market_pair: CrossExchangeMarketPair = CrossExchangeMarketPair(
            MarketTradingPairTuple(self.maker_market, *self.maker_trading_pairs),
            MarketTradingPairTuple(self.taker_market, *self.taker_trading_pairs),
        )

        logging_options: int = (
            CrossExchangeMarketMakingStrategy.OPTION_LOG_ALL
            & (~CrossExchangeMarketMakingStrategy.OPTION_LOG_NULL_ORDER_SIZE)
        )
        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy(
            [self.market_pair],
            order_size_portfolio_ratio_limit=Decimal("0.3"),
            min_profitability=Decimal(self.min_profitbality),
            logging_options=logging_options,
        )
        self.strategy_with_top_depth_tolerance: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy(
            [self.market_pair],
            order_size_portfolio_ratio_limit=Decimal("0.3"),
            min_profitability=Decimal(self.min_profitbality),
            logging_options=logging_options,
            top_depth_tolerance=1
        )
        self.logging_options = logging_options
        self.clock.add_iterator(self.maker_market)
        self.clock.add_iterator(self.taker_market)
        self.clock.add_iterator(self.strategy)

        self.maker_order_fill_logger: EventLogger = EventLogger()
        self.taker_order_fill_logger: EventLogger = EventLogger()
        self.cancel_order_logger: EventLogger = EventLogger()
        self.maker_order_created_logger: EventLogger = EventLogger()
        self.taker_order_created_logger: EventLogger = EventLogger()
        self.maker_market.add_listener(MarketEvent.OrderFilled, self.maker_order_fill_logger)
        self.taker_market.add_listener(MarketEvent.OrderFilled, self.taker_order_fill_logger)
        self.maker_market.add_listener(MarketEvent.OrderCancelled, self.cancel_order_logger)
        self.maker_market.add_listener(MarketEvent.BuyOrderCreated, self.maker_order_created_logger)
        self.maker_market.add_listener(MarketEvent.SellOrderCreated, self.maker_order_created_logger)
        self.taker_market.add_listener(MarketEvent.BuyOrderCreated, self.taker_order_created_logger)
        self.taker_market.add_listener(MarketEvent.SellOrderCreated, self.taker_order_created_logger)

    def simulate_maker_market_trade(self, is_buy: bool, quantity: Decimal, price: Decimal):
        maker_trading_pair: str = self.maker_trading_pairs[0]
        order_book: OrderBook = self.maker_market.get_order_book(maker_trading_pair)
        trade_event: OrderBookTradeEvent = OrderBookTradeEvent(
            maker_trading_pair, self.clock.current_timestamp, TradeType.BUY if is_buy else TradeType.SELL, price, quantity
        )
        order_book.apply_trade(trade_event)

    @staticmethod
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

    @staticmethod
    def simulate_limit_order_fill(market: Market, limit_order: LimitOrder):
        quote_currency_traded: Decimal = limit_order.price * limit_order.quantity
        base_currency_traded: Decimal = limit_order.quantity
        quote_currency: str = limit_order.quote_currency
        base_currency: str = limit_order.base_currency
        config: MarketConfig = market.config

        if limit_order.is_buy:
            market.set_balance(quote_currency, market.get_balance(quote_currency) - quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) + base_currency_traded)
            market.trigger_event(
                MarketEvent.BuyOrderCreated,
                BuyOrderCreatedEvent(
                    market.current_timestamp,
                    OrderType.LIMIT,
                    limit_order.trading_pair,
                    limit_order.quantity,
                    limit_order.price,
                    limit_order.client_order_id
                )
            )
            market.trigger_event(
                MarketEvent.OrderFilled,
                OrderFilledEvent(
                    market.current_timestamp,
                    limit_order.client_order_id,
                    limit_order.trading_pair,
                    TradeType.BUY,
                    OrderType.LIMIT,
                    limit_order.price,
                    limit_order.quantity,
                    TradeFee(Decimal(0)),
                ),
            )
            market.trigger_event(
                MarketEvent.BuyOrderCompleted,
                BuyOrderCompletedEvent(
                    market.current_timestamp,
                    limit_order.client_order_id,
                    base_currency,
                    quote_currency,
                    base_currency if config.buy_fees_asset is AssetType.BASE_CURRENCY else quote_currency,
                    base_currency_traded,
                    quote_currency_traded,
                    Decimal(0),
                    OrderType.LIMIT,
                ),
            )
        else:
            market.set_balance(quote_currency, market.get_balance(quote_currency) + quote_currency_traded)
            market.set_balance(base_currency, market.get_balance(base_currency) - base_currency_traded)
            market.trigger_event(
                MarketEvent.BuyOrderCreated,
                SellOrderCreatedEvent(
                    market.current_timestamp,
                    OrderType.LIMIT,
                    limit_order.trading_pair,
                    limit_order.quantity,
                    limit_order.price,
                    limit_order.client_order_id
                )
            )
            market.trigger_event(
                MarketEvent.OrderFilled,
                OrderFilledEvent(
                    market.current_timestamp,
                    limit_order.client_order_id,
                    limit_order.trading_pair,
                    TradeType.SELL,
                    OrderType.LIMIT,
                    limit_order.price,
                    limit_order.quantity,
                    TradeFee(Decimal(0)),
                ),
            )
            market.trigger_event(
                MarketEvent.SellOrderCompleted,
                SellOrderCompletedEvent(
                    market.current_timestamp,
                    limit_order.client_order_id,
                    base_currency,
                    quote_currency,
                    base_currency if config.sell_fees_asset is AssetType.BASE_CURRENCY else quote_currency,
                    base_currency_traded,
                    quote_currency_traded,
                    Decimal(0),
                    OrderType.LIMIT,
                ),
            )

    def test_both_sides_profitable(self):
        self.clock.backtest_til(self.start_timestamp + 5)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("0.99452"), bid_order.price)
        self.assertEqual(Decimal("1.0056"), ask_order.price)
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

        self.simulate_maker_market_trade(False, Decimal("10.0"), bid_order.price * Decimal("0.99"))

        self.clock.backtest_til(self.start_timestamp + 10)
        self.assertEqual(1, len(self.maker_order_fill_logger.event_log))
        self.assertEqual(1, len(self.taker_order_fill_logger.event_log))

        maker_fill: OrderFilledEvent = self.maker_order_fill_logger.event_log[0]
        taker_fill: OrderFilledEvent = self.taker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.BUY, maker_fill.trade_type)
        self.assertEqual(TradeType.SELL, taker_fill.trade_type)
        self.assertAlmostEqual(Decimal("0.99452"), maker_fill.price)
        self.assertAlmostEqual(Decimal("0.9995"), taker_fill.price)
        self.assertAlmostEqual(Decimal("3.0"), maker_fill.amount)
        self.assertAlmostEqual(Decimal("3.0"), taker_fill.amount)

    def test_top_depth_tolerance(self):  # TODO
        self.clock.remove_iterator(self.strategy)
        self.clock.add_iterator(self.strategy_with_top_depth_tolerance)
        self.clock.backtest_til(self.start_timestamp + 5)
        bid_order: LimitOrder = self.strategy_with_top_depth_tolerance.active_bids[0][1]
        ask_order: LimitOrder = self.strategy_with_top_depth_tolerance.active_asks[0][1]

        self.taker_market.trigger_event(
            MarketEvent.BuyOrderCreated,
            BuyOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                bid_order.trading_pair,
                bid_order.quantity,
                bid_order.price,
                bid_order.client_order_id
            )
        )

        self.taker_market.trigger_event(
            MarketEvent.SellOrderCreated,
            SellOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                ask_order.trading_pair,
                ask_order.quantity,
                ask_order.price,
                ask_order.client_order_id
            )
        )

        self.assertEqual(Decimal("0.99452"), bid_order.price)
        self.assertEqual(Decimal("1.0056"), ask_order.price)
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

        self.simulate_order_book_widening(self.taker_data.order_book, 0.99, 1.01)

        self.clock.backtest_til(self.start_timestamp + 100)

        self.assertEqual(2, len(self.cancel_order_logger.event_log))
        self.assertEqual(1, len(self.strategy_with_top_depth_tolerance.active_bids))
        self.assertEqual(1, len(self.strategy_with_top_depth_tolerance.active_asks))

        bid_order = self.strategy_with_top_depth_tolerance.active_bids[0][1]
        ask_order = self.strategy_with_top_depth_tolerance.active_asks[0][1]
        self.assertEqual(Decimal("0.98457"), bid_order.price)
        self.assertEqual(Decimal("1.0156"), ask_order.price)

    def test_market_became_wider(self):  # TODO
        self.clock.backtest_til(self.start_timestamp + 5)

        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("0.99452"), bid_order.price)
        self.assertEqual(Decimal("1.0056"), ask_order.price)
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

        self.taker_market.trigger_event(
            MarketEvent.BuyOrderCreated,
            BuyOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                bid_order.trading_pair,
                bid_order.quantity,
                bid_order.price,
                bid_order.client_order_id
            )
        )

        self.taker_market.trigger_event(
            MarketEvent.SellOrderCreated,
            SellOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                ask_order.trading_pair,
                ask_order.quantity,
                ask_order.price,
                ask_order.client_order_id
            )
        )

        self.simulate_order_book_widening(self.taker_data.order_book, 0.99, 1.01)

        self.clock.backtest_til(self.start_timestamp + 100)

        self.assertEqual(2, len(self.cancel_order_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        bid_order = self.strategy.active_bids[0][1]
        ask_order = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("0.98457"), bid_order.price)
        self.assertEqual(Decimal("1.0156"), ask_order.price)

    def test_market_became_narrower(self):
        self.clock.backtest_til(self.start_timestamp + 5)
        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("0.99452"), bid_order.price)
        self.assertEqual(Decimal("1.0056"), ask_order.price)
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

        self.maker_data.order_book.apply_diffs([OrderBookRow(0.996, 30, 2)], [OrderBookRow(1.004, 30, 2)], 2)

        self.clock.backtest_til(self.start_timestamp + 10)
        self.assertEqual(0, len(self.cancel_order_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        bid_order = self.strategy.active_bids[0][1]
        ask_order = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("0.99452"), bid_order.price)
        self.assertEqual(Decimal("1.0056"), ask_order.price)

    def test_order_fills_after_cancellation(self):  # TODO
        self.clock.backtest_til(self.start_timestamp + 5)
        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("0.99452"), bid_order.price)
        self.assertEqual(Decimal("1.0056"), ask_order.price)
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

        self.taker_market.trigger_event(
            MarketEvent.BuyOrderCreated,
            BuyOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                bid_order.trading_pair,
                bid_order.quantity,
                bid_order.price,
                bid_order.client_order_id
            )
        )

        self.taker_market.trigger_event(
            MarketEvent.SellOrderCreated,
            SellOrderCreatedEvent(
                self.start_timestamp + 5,
                OrderType.LIMIT,
                ask_order.trading_pair,
                ask_order.quantity,
                ask_order.price,
                ask_order.client_order_id
            )
        )

        self.simulate_order_book_widening(self.taker_data.order_book, 0.99, 1.01)

        self.clock.backtest_til(self.start_timestamp + 10)

        self.assertEqual(2, len(self.cancel_order_logger.event_log))
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))

        bid_order = self.strategy.active_bids[0][1]
        ask_order = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("0.98457"), bid_order.price)
        self.assertEqual(Decimal("1.0156"), ask_order.price)

        self.clock.backtest_til(self.start_timestamp + 20)
        self.simulate_limit_order_fill(self.maker_market, bid_order)
        self.simulate_limit_order_fill(self.maker_market, ask_order)

        self.clock.backtest_til(self.start_timestamp + 25)
        fill_events: List[OrderFilledEvent] = self.taker_order_fill_logger.event_log
        bid_hedges: List[OrderFilledEvent] = [evt for evt in fill_events if evt.trade_type is TradeType.SELL]
        ask_hedges: List[OrderFilledEvent] = [evt for evt in fill_events if evt.trade_type is TradeType.BUY]
        self.assertEqual(1, len(bid_hedges))
        self.assertEqual(1, len(ask_hedges))
        self.assertGreater(
            self.maker_market.get_balance(self.maker_trading_pairs[2]) + self.taker_market.get_balance(self.taker_trading_pairs[2]),
            Decimal("10"),
        )
        self.assertEqual(2, len(self.taker_order_fill_logger.event_log))
        taker_fill1: OrderFilledEvent = self.taker_order_fill_logger.event_log[0]
        self.assertEqual(TradeType.SELL, taker_fill1.trade_type)
        self.assertAlmostEqual(Decimal("0.9895"), taker_fill1.price)
        self.assertAlmostEqual(Decimal("3.0"), taker_fill1.amount)
        taker_fill2: OrderFilledEvent = self.taker_order_fill_logger.event_log[1]
        self.assertEqual(TradeType.BUY, taker_fill2.trade_type)
        self.assertAlmostEqual(Decimal("1.0105"), taker_fill2.price)
        self.assertAlmostEqual(Decimal("3.0"), taker_fill2.amount)

    def test_with_conversion(self):
        self.clock.remove_iterator(self.strategy)
        self.market_pair: CrossExchangeMarketPair = CrossExchangeMarketPair(
            MarketTradingPairTuple(self.maker_market, *["COINALPHA-QETH", "COINALPHA", "QETH"]),
            MarketTradingPairTuple(self.taker_market, *self.taker_trading_pairs),
        )
        self.maker_data: MockOrderBookLoader = MockOrderBookLoader("COINALPHA-QETH", "COINALPHA", "QETH")
        self.maker_data.set_balanced_order_book(1.05, 0.55, 1.55, 0.01, 10)
        self.maker_market.add_data(self.maker_data)
        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy(
            [self.market_pair], Decimal("0.01"),
            order_size_portfolio_ratio_limit=Decimal("0.3"),
            logging_options=self.logging_options,
            taker_to_maker_base_conversion_rate=Decimal("0.95")
        )
        self.clock.add_iterator(self.strategy)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))
        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertAlmostEqual(Decimal("1.0417"), round(bid_order.price, 4))
        self.assertAlmostEqual(Decimal("1.0637"), round(ask_order.price, 4))
        self.assertAlmostEqual(Decimal("2.9286"), round(bid_order.quantity, 4))
        self.assertAlmostEqual(Decimal("2.9286"), round(ask_order.quantity, 4))

    def test_maker_price(self):
        buy_taker_price: Decimal = self.strategy.get_effective_hedging_price(self.market_pair, False, 3)
        sell_taker_price: Decimal = self.strategy.get_effective_hedging_price(self.market_pair, True, 3)
        price_quantum = Decimal("0.0001")
        self.assertEqual(Decimal("1.0005"), buy_taker_price)
        self.assertEqual(Decimal("0.9995"), sell_taker_price)
        self.clock.backtest_til(self.start_timestamp + 5)
        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        bid_maker_price = sell_taker_price * (1 - self.min_profitbality)
        bid_maker_price = (floor(bid_maker_price / price_quantum)) * price_quantum
        ask_maker_price = buy_taker_price * (1 + self.min_profitbality)
        ask_maker_price = (ceil(ask_maker_price / price_quantum) * price_quantum)
        self.assertEqual(bid_maker_price, round(bid_order.price, 4))
        self.assertEqual(ask_maker_price, round(ask_order.price, 4))
        self.assertEqual(Decimal("3.0"), bid_order.quantity)
        self.assertEqual(Decimal("3.0"), ask_order.quantity)

    def test_with_adjust_orders_enabled(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.remove_iterator(self.maker_market)
        self.maker_market: BacktestMarket = BacktestMarket()

        self.maker_data: MockOrderBookLoader = MockOrderBookLoader(*self.maker_trading_pairs)
        self.maker_data.set_balanced_order_book(1.0, 0.5, 1.5, 0.1, 10)
        self.maker_market.add_data(self.maker_data)
        self.market_pair: CrossExchangeMarketPair = CrossExchangeMarketPair(
            MarketTradingPairTuple(self.maker_market, *self.maker_trading_pairs),
            MarketTradingPairTuple(self.taker_market, *self.taker_trading_pairs),
        )
        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy(
            [self.market_pair],
            order_size_portfolio_ratio_limit=Decimal("0.3"),
            min_profitability=Decimal("0.005"),
            logging_options=self.logging_options,
        )
        self.maker_market.set_balance("COINALPHA", 5)
        self.maker_market.set_balance("WETH", 5)
        self.maker_market.set_balance("QETH", 5)
        self.maker_market.set_quantization_param(QuantizationParams(self.maker_trading_pairs[0], 4, 4, 4, 4))
        self.clock.add_iterator(self.strategy)
        self.clock.add_iterator(self.maker_market)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))
        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        # place above top bid (at 0.95)
        self.assertAlmostEqual(Decimal("0.9501"), bid_order.price)
        # place below top ask (at 1.05)
        self.assertAlmostEqual(Decimal("1.049"), ask_order.price)
        self.assertAlmostEqual(Decimal("3"), round(bid_order.quantity, 4))
        self.assertAlmostEqual(Decimal("3"), round(ask_order.quantity, 4))

    def test_with_adjust_orders_disabled(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.remove_iterator(self.maker_market)
        self.maker_market: BacktestMarket = BacktestMarket()

        self.maker_data: MockOrderBookLoader = MockOrderBookLoader(*self.maker_trading_pairs)
        self.maker_data.set_balanced_order_book(1.0, 0.5, 1.5, 0.1, 10)
        self.taker_data.set_balanced_order_book(1.0, 0.5, 1.5, 0.001, 20)
        self.maker_market.add_data(self.maker_data)
        self.market_pair: CrossExchangeMarketPair = CrossExchangeMarketPair(
            MarketTradingPairTuple(self.maker_market, *self.maker_trading_pairs),
            MarketTradingPairTuple(self.taker_market, *self.taker_trading_pairs),
        )
        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy(
            [self.market_pair],
            order_size_portfolio_ratio_limit=Decimal("0.3"),
            min_profitability=Decimal("0.005"),
            logging_options=self.logging_options,
            adjust_order_enabled=False
        )
        self.maker_market.set_balance("COINALPHA", 5)
        self.maker_market.set_balance("WETH", 5)
        self.maker_market.set_balance("QETH", 5)
        self.maker_market.set_quantization_param(QuantizationParams(self.maker_trading_pairs[0], 4, 4, 4, 4))
        self.clock.add_iterator(self.strategy)
        self.clock.add_iterator(self.maker_market)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))
        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        self.assertEqual(Decimal("0.9945"), bid_order.price)
        self.assertEqual(Decimal("1.006"), ask_order.price)
        self.assertAlmostEqual(Decimal("3"), round(bid_order.quantity, 4))
        self.assertAlmostEqual(Decimal("3"), round(ask_order.quantity, 4))

    def test_price_and_size_limit_calculation(self):
        self.taker_data.set_balanced_order_book(1.0, 0.5, 1.5, 0.001, 20)
        bid_size = self.strategy.get_market_making_size(self.market_pair, True)
        bid_price = self.strategy.get_market_making_price(self.market_pair, True, bid_size)
        ask_size = self.strategy.get_market_making_size(self.market_pair, False)
        ask_price = self.strategy.get_market_making_price(self.market_pair, False, ask_size)
        self.assertEqual((Decimal("0.99452"), Decimal("3")), (bid_price, bid_size))
        self.assertEqual((Decimal("1.0056"), Decimal("3")), (ask_price, ask_size))

    def test_empty_maker_orderbook(self):
        self.clock.remove_iterator(self.strategy)
        self.clock.remove_iterator(self.maker_market)
        self.maker_market: BacktestMarket = BacktestMarket()

        self.maker_data: MockOrderBookLoader = MockOrderBookLoader(*self.maker_trading_pairs)
        # Orderbook is empty
        self.maker_market.add_data(self.maker_data)
        self.market_pair: CrossExchangeMarketPair = CrossExchangeMarketPair(
            MarketTradingPairTuple(self.maker_market, *self.maker_trading_pairs),
            MarketTradingPairTuple(self.taker_market, *self.taker_trading_pairs),
        )
        self.strategy: CrossExchangeMarketMakingStrategy = CrossExchangeMarketMakingStrategy(
            [self.market_pair],
            order_amount=1,
            min_profitability=Decimal("0.005"),
            logging_options=self.logging_options,
            adjust_order_enabled=False
        )
        self.maker_market.set_balance("COINALPHA", 5)
        self.maker_market.set_balance("WETH", 5)
        self.maker_market.set_balance("QETH", 5)
        self.maker_market.set_quantization_param(QuantizationParams(self.maker_trading_pairs[0], 4, 4, 4, 4))
        self.clock.add_iterator(self.strategy)
        self.clock.add_iterator(self.maker_market)
        self.clock.backtest_til(self.start_timestamp + 5)
        self.assertEqual(1, len(self.strategy.active_bids))
        self.assertEqual(1, len(self.strategy.active_asks))
        bid_order: LimitOrder = self.strategy.active_bids[0][1]
        ask_order: LimitOrder = self.strategy.active_asks[0][1]
        # Places orders based on taker orderbook
        self.assertEqual(Decimal("0.9945"), bid_order.price)
        self.assertEqual(Decimal("1.006"), ask_order.price)
        self.assertAlmostEqual(Decimal("1"), round(bid_order.quantity, 4))
        self.assertAlmostEqual(Decimal("1"), round(ask_order.quantity, 4))
