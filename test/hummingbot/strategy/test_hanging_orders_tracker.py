from datetime import datetime
import logging
import unittest
from decimal import Decimal
from mock import MagicMock, patch, PropertyMock

from hummingbot.core.event.events import MarketEvent, OrderCancelledEvent, BuyOrderCompletedEvent
from hummingbot.strategy.hanging_orders_tracker import HangingOrdersTracker, HangingOrdersAggregationType
from hummingbot.strategy.data_types import HangingOrder, OrderType
from hummingbot.core.data_type.limit_order import LimitOrder


class TestHangingOrdersTracker(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = self.create_mock_strategy()
        self.tracker = HangingOrdersTracker(self.strategy, hanging_orders_cancel_pct=Decimal("0.1"))

    @staticmethod
    def quantize_order_amount(trading_pair: str, amount: Decimal):
        return amount.quantize(Decimal("0.00001"))

    @staticmethod
    def quantize_order_price(trading_pair: str, price: Decimal):
        return price.quantize(Decimal("0.00001"))

    def create_mock_strategy(self):
        market = MagicMock()
        market.quantize_order_amount.side_effect = self.quantize_order_amount
        market.quantize_order_price.side_effect = self.quantize_order_price
        market.get_maker_order_type.return_value = OrderType.LIMIT

        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock()
        type(strategy).max_order_age = PropertyMock(return_value=1800.0)
        type(strategy).order_refresh_time = PropertyMock(return_value=45.0)
        strategy.get_price.return_value = Decimal("100.0")
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="BTC-USDT")

        return strategy

    def test_tracker_initialized(self):
        self.assertEqual(self.tracker.trading_pair, "BTC-USDT")
        self.assertEqual(self.tracker.original_orders, set())
        self.assertEqual(self.tracker.strategy_current_hanging_orders, set())
        self.assertEqual(self.tracker.current_created_pairs_of_orders, list())

    def test_add_remove_limit_order(self):
        order_to_add = LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1))
        self.tracker.add_order(order_to_add)
        self.assertEqual(len(self.tracker.original_orders), 1)
        order_that_doesnt_belong = LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(100),
                                              Decimal(1))
        self.tracker.remove_order(order_that_doesnt_belong)
        self.assertEqual(len(self.tracker.original_orders), 1)
        self.tracker.remove_order(order_to_add)
        self.assertEqual(len(self.tracker.original_orders), 0)
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", True, "BTC", "USDT", Decimal(100), Decimal(1)))
        self.tracker.remove_all_orders()
        self.assertEqual(len(self.tracker.original_orders), 0)

    def test_remove_orders_far_from_price(self):
        # hanging_orders_cancel_pct = 10% so will add one closer and one further
        # Current price = 100.0
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", False, "BTC", "USDT", Decimal(101), Decimal(1)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", False, "BTC", "USDT", Decimal(120), Decimal(1)))
        self.assertEqual(len(self.tracker.original_orders), 2)
        self.tracker.remove_orders_far_from_price()
        self.assertEqual(len(self.tracker.original_orders), 1)

    def test_renew_hanging_orders_past_max_order_age(self):
        cancelled_orders_ids = []
        strategy_active_orders = []
        type(self.strategy).current_timestamp = PropertyMock(return_value=1234967891)
        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.cancel_order.side_effect = lambda order_id: cancelled_orders_ids.append(order_id)
        self.strategy.buy_with_specific_market.return_value = "Order-1234569990000000"

        # Order just executed
        new_order = LimitOrder("Order-1234567890000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(101),
                               Decimal(1))
        # Order executed 1900 seconds ago
        old_order = LimitOrder("Order-1234565991000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(105),
                               Decimal(1))

        self.tracker.add_order(new_order)
        strategy_active_orders.append(new_order)
        self.tracker.add_order(old_order)
        strategy_active_orders.append(old_order)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        self.assertTrue(any(order.trading_pair == "BTC-USDT" and order.price == Decimal(105)
                            for order
                            in self.tracker.strategy_current_hanging_orders))

        # When calling the renew logic, the old order should start the renew process (it should be canceled)
        # but it will only stop being a current hanging order once the cancel confirmation arrives
        self.tracker.process_tick()
        self.assertTrue(old_order.client_order_id in cancelled_orders_ids)
        self.assertTrue(any(order.trading_pair == "BTC-USDT" and order.price == Decimal(105)
                            for order
                            in self.tracker.strategy_current_hanging_orders))

        # When the cancel is confirmed the order should no longer be considered a hanging order
        strategy_active_orders.remove(old_order)
        self.tracker._did_cancel_order(MarketEvent.OrderCancelled,
                                       self,
                                       OrderCancelledEvent(old_order.client_order_id, old_order.client_order_id))
        self.assertFalse(any(order.order_id == old_order.client_order_id for order
                             in self.tracker.strategy_current_hanging_orders))
        self.assertTrue(any(order.order_id == "Order-1234569990000000" for order
                            in self.tracker.strategy_current_hanging_orders))

    def test_hanging_order_being_renewed_discarded_if_not_current_hanging_order_after_cancel(self):
        cancelled_orders_ids = []
        strategy_active_orders = []

        newly_created_orders_ids = ["Order-1234569990000000", "Order-1234570000000000"]

        type(self.strategy).current_timestamp = PropertyMock(return_value=1234900000)
        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.cancel_order.side_effect = lambda order_id: cancelled_orders_ids.append(order_id)
        self.strategy.buy_with_specific_market.side_effect = newly_created_orders_ids

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_TIME_WEIGHTED)

        # Order just executed
        new_order = LimitOrder("Order-1234567890000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(101),
                               Decimal(1))
        # Order executed 1900 seconds ago
        old_order = LimitOrder("Order-1234565991000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(105),
                               Decimal(1))

        self.tracker.add_order(old_order)
        strategy_active_orders.append(old_order)
        self.tracker.update_strategy_orders_with_equivalent_orders()

        # A new order should have been created.
        self.assertTrue(any(order.order_id == newly_created_orders_ids[0] for order
                            in self.tracker.strategy_current_hanging_orders))

        hanging_order = next(iter(self.tracker.strategy_current_hanging_orders))
        strategy_active_orders.append(LimitOrder(hanging_order.order_id,
                                                 hanging_order.trading_pair,
                                                 hanging_order.is_buy,
                                                 hanging_order.base_asset,
                                                 hanging_order.quote_asset,
                                                 hanging_order.price,
                                                 hanging_order.amount))

        # When calling the renew logic, the old order should start the renew process (it should be canceled)
        # but it will only stop being a current hanging order once the cancel confirmation arrives
        self.tracker.process_tick()
        self.assertTrue(newly_created_orders_ids[0] in cancelled_orders_ids)
        self.assertTrue(any(order.order_id == newly_created_orders_ids[0] for order
                            in self.tracker.strategy_current_hanging_orders))

        # Before cancellation is confirmed a new order is added to the tracker, generating a new grouped hanging order
        self.tracker.add_order(new_order)
        strategy_active_orders.append(new_order)
        self.tracker.update_strategy_orders_with_equivalent_orders()

        # When the cancel is confirmed the order should no longer be considered a hanging order
        strategy_active_orders.remove(old_order)
        self.tracker._did_cancel_order(MarketEvent.OrderCancelled,
                                       self,
                                       OrderCancelledEvent(old_order.client_order_id, old_order.client_order_id))
        self.assertFalse(any(order.order_id == old_order.client_order_id for order
                             in self.tracker.strategy_current_hanging_orders))
        self.assertTrue(any(order.order_id == "Order-1234569990000000" for order
                            in self.tracker.strategy_current_hanging_orders))

    def test_asymmetrical_volume_weighted(self):
        # Asymmetrical in distance to mid-price and amounts
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(2)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(95), Decimal(1)))
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", False, "BTC", "USDT", Decimal(94), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_WEIGHTED)
        self.tracker.update_strategy_orders_with_equivalent_orders()
        self.assertEqual(self.tracker.strategy_current_hanging_orders,
                         {HangingOrder(order_id=None,
                                       trading_pair='BTC-USDT',
                                       is_buy=True,
                                       price=Decimal('97.66667'),
                                       amount=Decimal('3.00000')),
                          HangingOrder(order_id=None,
                                       trading_pair='BTC-USDT',
                                       is_buy=False,
                                       price=Decimal('107.36364'),
                                       amount=Decimal('11.00000'))})

    def test_symmetrical_volume_weighted(self):
        # Symmetrical in distance to mid-price and amounts
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(91), Decimal(5)))
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", False, "BTC", "USDT", Decimal(101), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_WEIGHTED)
        self.tracker.update_strategy_orders_with_equivalent_orders()
        self.assertEqual(self.tracker.strategy_current_hanging_orders,
                         {HangingOrder(order_id=None,
                                       trading_pair='BTC-USDT',
                                       is_buy=True,
                                       price=Decimal('95.36364'),
                                       amount=Decimal('11.00000')),
                          HangingOrder(order_id=None,
                                       trading_pair='BTC-USDT',
                                       is_buy=False,
                                       price=Decimal('104.63636'),
                                       amount=Decimal('11.00000'))})

    def test_asymmetrical_volume_age_weighted(self):
        current_time_mock = 1234567891
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 500}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(2)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 600}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(95), Decimal(1)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 700}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(94), Decimal(6)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 800}000000",
                                          "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))
        with patch('time.time', return_value=current_time_mock):
            self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_TIME_WEIGHTED)
            self.tracker.update_strategy_orders_with_equivalent_orders()
            self.assertEqual(self.tracker.strategy_current_hanging_orders,
                             {HangingOrder(order_id=None,
                                           trading_pair='BTC-USDT',
                                           is_buy=True,
                                           price=Decimal('95.31641'),
                                           amount=Decimal('9.00000')),
                              HangingOrder(order_id=None,
                                           trading_pair='BTC-USDT',
                                           is_buy=False,
                                           price=Decimal('109.00000'),
                                           amount=Decimal('5.00000'))})

    def test_symmetrical_volume_age_weighted(self):
        # Symmetrical in distance to mid-price and amounts, BUT different ages
        current_time_mock = 1234567891
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 300}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(6)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 600}000000",
                                          "BTC-USDT", True, "BTC", "USDT", Decimal(91), Decimal(5)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 800}000000",
                                          "BTC-USDT", False, "BTC", "USDT", Decimal(101), Decimal(6)))
        self.tracker.add_order(LimitOrder(f"Order-{current_time_mock - 1200}000000",
                                          "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        with patch('time.time', return_value=current_time_mock):
            self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_TIME_WEIGHTED)
            self.tracker.update_strategy_orders_with_equivalent_orders()
            self.assertEqual(self.tracker.strategy_current_hanging_orders,
                             {HangingOrder(order_id=None,
                                           trading_pair='BTC-USDT',
                                           is_buy=True,
                                           price=Decimal('95.69098'),
                                           amount=Decimal('11.00000')),
                              HangingOrder(order_id=None,
                                           trading_pair='BTC-USDT',
                                           is_buy=False,
                                           price=Decimal('104.20177'),
                                           amount=Decimal('11.00000'))})

    def test_asymmetrical_volume_distance_weighted(self):
        # Asymmetrical in distance to mid-price and amounts, BUT with distance affecting the weight exponentially
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(2)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(95), Decimal(1)))
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", False, "BTC", "USDT", Decimal(94), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_DISTANCE_WEIGHTED)
        self.tracker.update_strategy_orders_with_equivalent_orders()
        self.assertEqual(self.tracker.strategy_current_hanging_orders,
                         {HangingOrder(order_id=None,
                                       trading_pair='BTC-USDT',
                                       is_buy=False,
                                       price=Decimal('107.14511'),
                                       amount=Decimal('11.00000')),
                          HangingOrder(order_id=None,
                                       trading_pair='BTC-USDT',
                                       is_buy=True,
                                       price=Decimal('97.99590'),
                                       amount=Decimal('3.00000'))})

    def test_symmetrical_volume_distance_weighted(self):
        # Symmetrical in distance to mid-price and amounts, BUT with distance affecting the weight exponentially
        self.tracker.add_order(LimitOrder("Order-number-1", "BTC-USDT", True, "BTC", "USDT", Decimal(99), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-2", "BTC-USDT", True, "BTC", "USDT", Decimal(91), Decimal(5)))
        self.tracker.add_order(LimitOrder("Order-number-3", "BTC-USDT", False, "BTC", "USDT", Decimal(101), Decimal(6)))
        self.tracker.add_order(LimitOrder("Order-number-4", "BTC-USDT", False, "BTC", "USDT", Decimal(109), Decimal(5)))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_DISTANCE_WEIGHTED)
        self.tracker.update_strategy_orders_with_equivalent_orders()
        self.assertEqual(self.tracker.strategy_current_hanging_orders,
                         {HangingOrder(order_id=None,
                                       trading_pair='BTC-USDT',
                                       is_buy=True,
                                       price=Decimal('96.82055'),
                                       amount=Decimal('11.00000')),
                          HangingOrder(order_id=None,
                                       trading_pair='BTC-USDT',
                                       is_buy=False,
                                       price=Decimal('103.17945'),
                                       amount=Decimal('11.00000'))})

    def test_hanging_order_removed_when_cancelled(self):
        strategy_active_orders = []
        strategy_logs = []
        app_notifications = []

        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.log_with_clock.side_effect = lambda log_type, message: strategy_logs.append((log_type, message))
        self.strategy.notify_hb_app.side_effect = lambda message: app_notifications.append(message)

        new_order = LimitOrder("Order-1234567890000000",
                               "BTC-USDT",
                               True,
                               "BTC",
                               "USDT",
                               Decimal(101),
                               Decimal(1))

        self.tracker.add_order(new_order)
        strategy_active_orders.append(new_order)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        # Now we simulate the order is cancelled
        self.tracker._did_cancel_order(MarketEvent.OrderCancelled,
                                       self,
                                       OrderCancelledEvent(new_order.client_order_id, new_order.client_order_id))

        self.assertIn((logging.INFO, "(BTC-USDT) Hanging order Order-1234567890000000 cancelled."), strategy_logs)
        self.assertIn("(BTC-USDT) Hanging order Order-1234567890000000 cancelled.", app_notifications)
        self.assertTrue(len(self.tracker.strategy_current_hanging_orders) == 0)
        self.assertNotIn(new_order, self.tracker.original_orders)

    def test_grouped_hanging_order_and_original_orders_removed_when_hanging_order_completed(self):
        strategy_active_orders = []
        newly_created_buy_orders_ids = ["Order-1234570000000000",
                                        "Order-1234570010000000",
                                        "Order-1234570020000000",
                                        "Order-1234570030000000"]

        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.buy_with_specific_market.side_effect = newly_created_buy_orders_ids

        # Order just executed
        buy_order_1 = LimitOrder("Order-1234569960000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(101),
                                 Decimal(1))
        buy_order_2 = LimitOrder("Order-1234569980000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(105),
                                 Decimal(1))

        sell_order_1 = LimitOrder("Order-1234569970000000",
                                  "BTC-USDT",
                                  False,
                                  "BTC",
                                  "USDT",
                                  Decimal(110),
                                  Decimal(1))
        sell_order_2 = LimitOrder("Order-1234569990000000",
                                  "BTC-USDT",
                                  False,
                                  "BTC",
                                  "USDT",
                                  Decimal(115),
                                  Decimal(1))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.VOLUME_WEIGHTED)

        self.tracker.add_order(buy_order_1)
        strategy_active_orders.append(buy_order_1)
        self.tracker.add_order(buy_order_2)
        strategy_active_orders.append(buy_order_2)
        self.tracker.add_order(sell_order_1)
        strategy_active_orders.append(sell_order_1)
        self.tracker.add_order(sell_order_2)
        strategy_active_orders.append(sell_order_2)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        buy_hanging_order = next(order for order in self.tracker.strategy_current_hanging_orders if order.is_buy)
        sell_hanging_order = next(order for order in self.tracker.strategy_current_hanging_orders if not order.is_buy)
        strategy_active_orders.remove(buy_order_1)
        strategy_active_orders.remove(buy_order_2)
        strategy_active_orders.append(buy_hanging_order)
        strategy_active_orders.append(sell_hanging_order)

        self.assertEqual(4, len(self.tracker.original_orders))
        self.assertEqual(2, len(self.tracker.strategy_current_hanging_orders))

        # Now we simulate the buy hanging order being fully filled
        strategy_active_orders.remove(buy_hanging_order)
        self.tracker._did_complete_buy_order(MarketEvent.BuyOrderCompleted,
                                             self,
                                             BuyOrderCompletedEvent(
                                                 timestamp=datetime.now().timestamp(),
                                                 order_id=buy_hanging_order.order_id,
                                                 base_asset="BTC",
                                                 quote_asset="USDT",
                                                 fee_asset="USDT",
                                                 base_asset_amount=buy_hanging_order.amount,
                                                 quote_asset_amount=buy_hanging_order.amount * buy_hanging_order.price,
                                                 fee_amount=Decimal(0),
                                                 order_type=OrderType.LIMIT))

        self.assertEqual(1, len(self.tracker.strategy_current_hanging_orders))
        self.assertNotIn(buy_hanging_order, self.tracker.strategy_current_hanging_orders)
        self.assertEqual(2, len(self.tracker.original_orders))
        self.assertTrue(all(not order.is_buy for order in self.tracker.original_orders))

        # In this moment the only hanging order in the tracker is the generated by the two sells.
        # We add a new buy hanging order to test that fully filling the sell hanging order only removes the sells

        self.tracker.add_order(buy_order_1)
        strategy_active_orders.append(buy_order_1)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        buy_hanging_order = next(order for order in self.tracker.strategy_current_hanging_orders if order.is_buy)
        strategy_active_orders.remove(buy_order_1)
        strategy_active_orders.append(buy_hanging_order)

        self.assertEqual(3, len(self.tracker.original_orders))
        self.assertEqual(2, len(self.tracker.strategy_current_hanging_orders))

        # Now we simulate the sell hanging order being fully filled
        strategy_active_orders.remove(sell_hanging_order)
        self.tracker._did_complete_sell_order(MarketEvent.BuyOrderCompleted,
                                              self,
                                              BuyOrderCompletedEvent(
                                                  timestamp=datetime.now().timestamp(),
                                                  order_id=sell_hanging_order.order_id,
                                                  base_asset="BTC",
                                                  quote_asset="USDT",
                                                  fee_asset="USDT",
                                                  base_asset_amount=sell_hanging_order.amount,
                                                  quote_asset_amount=sell_hanging_order.amount * sell_hanging_order.price,
                                                  fee_amount=Decimal(0),
                                                  order_type=OrderType.LIMIT))

        self.assertEqual(1, len(self.tracker.strategy_current_hanging_orders))
        self.assertNotIn(sell_hanging_order, self.tracker.strategy_current_hanging_orders)
        self.assertEqual(1, len(self.tracker.original_orders))
        self.assertTrue(all(order.is_buy for order in self.tracker.original_orders))

    def test_non_grouped_hanging_order_and_original_order_removed_when_hanging_order_completed(self):
        strategy_active_orders = []
        newly_created_buy_orders_ids = ["Order-1234570000000000",
                                        "Order-1234570010000000",
                                        "Order-1234570020000000",
                                        "Order-1234570030000000"]

        type(self.strategy).active_orders = PropertyMock(return_value=strategy_active_orders)
        self.strategy.buy_with_specific_market.side_effect = newly_created_buy_orders_ids

        buy_order_1 = LimitOrder("Order-1234569960000000",
                                 "BTC-USDT",
                                 True,
                                 "BTC",
                                 "USDT",
                                 Decimal(101),
                                 Decimal(1))
        sell_order_1 = LimitOrder("Order-1234569970000000",
                                  "BTC-USDT",
                                  False,
                                  "BTC",
                                  "USDT",
                                  Decimal(110),
                                  Decimal(1))

        self.tracker.set_aggregation_method(HangingOrdersAggregationType.NO_AGGREGATION)

        self.tracker.add_order(buy_order_1)
        strategy_active_orders.append(buy_order_1)
        self.tracker.add_order(sell_order_1)
        strategy_active_orders.append(sell_order_1)

        self.tracker.update_strategy_orders_with_equivalent_orders()

        buy_hanging_order = next(order for order in self.tracker.strategy_current_hanging_orders if order.is_buy)
        sell_hanging_order = next(order for order in self.tracker.strategy_current_hanging_orders if not order.is_buy)

        self.assertEqual(buy_order_1.client_order_id, buy_hanging_order.order_id)
        self.assertEqual(sell_order_1.client_order_id, sell_hanging_order.order_id)
        self.assertEqual(2, len(self.tracker.original_orders))
        self.assertEqual(2, len(self.tracker.strategy_current_hanging_orders))

        # Now we simulate the buy hanging order being fully filled
        strategy_active_orders.remove(buy_order_1)
        self.tracker._did_complete_buy_order(MarketEvent.BuyOrderCompleted,
                                             self,
                                             BuyOrderCompletedEvent(
                                                 timestamp=datetime.now().timestamp(),
                                                 order_id=buy_order_1.client_order_id,
                                                 base_asset="BTC",
                                                 quote_asset="USDT",
                                                 fee_asset="USDT",
                                                 base_asset_amount=buy_order_1.quantity,
                                                 quote_asset_amount=buy_order_1.quantity * buy_order_1.price,
                                                 fee_amount=Decimal(0),
                                                 order_type=OrderType.LIMIT))

        self.assertEqual(1, len(self.tracker.strategy_current_hanging_orders))
        self.assertNotIn(buy_hanging_order, self.tracker.strategy_current_hanging_orders)
        self.assertEqual(1, len(self.tracker.original_orders))
        self.assertNotIn(buy_order_1, self.tracker.original_orders)
