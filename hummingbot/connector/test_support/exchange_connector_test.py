import asyncio
import json
import re
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict

from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus


class AbstractExchangeConnectorTests:
    """
    We need to create the abstract TestCase class inside another class not inheriting from TestCase to prevent test
    frameworks from discovering and tyring to run the abstract class
    """

    class ExchangeConnectorTests(ABC, TestCase):
        # the level is required to receive logs from the data source logger
        level = 0

        @property
        @abstractmethod
        def all_symbols_url(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def latest_prices_url(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def network_status_url(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def trading_rules_url(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def order_creation_url(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def balance_url(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def all_symbols_request_mock_response(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def latest_prices_request_mock_response(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
            raise NotImplementedError

        @property
        @abstractmethod
        def network_status_request_successful_mock_response(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def trading_rules_request_mock_response(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def trading_rules_request_erroneous_mock_response(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def order_creation_request_successful_mock_response(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def balance_request_mock_response_for_base_and_quote(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def balance_request_mock_response_only_base(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def balance_event_websocket_update(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def expected_latest_price(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def expected_supported_order_types(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def expected_trading_rule(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def expected_logged_error_for_erroneous_trading_rule(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def expected_exchange_order_id(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def is_cancel_request_executed_synchronously_by_server(self) -> bool:
            raise NotImplementedError

        @property
        @abstractmethod
        def is_order_fill_http_update_included_in_status_update(self) -> bool:
            raise NotImplementedError

        @property
        @abstractmethod
        def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
            raise NotImplementedError

        @property
        @abstractmethod
        def expected_partial_fill_price(self) -> Decimal:
            raise NotImplementedError

        @property
        @abstractmethod
        def expected_partial_fill_amount(self) -> Decimal:
            raise NotImplementedError

        @property
        @abstractmethod
        def expected_fill_fee(self) -> TradeFeeBase:
            raise NotImplementedError

        @property
        @abstractmethod
        def expected_fill_trade_id(self) -> str:
            raise NotImplementedError

        @abstractmethod
        def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
            raise NotImplementedError

        @abstractmethod
        def create_exchange_instance(self):
            raise NotImplementedError

        @abstractmethod
        def validate_auth_credentials_present(self, request_call: RequestCall):
            raise NotImplementedError

        @abstractmethod
        def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
            raise NotImplementedError

        @abstractmethod
        def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
            raise NotImplementedError

        @abstractmethod
        def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
            raise NotImplementedError

        @abstractmethod
        def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
            raise NotImplementedError

        @abstractmethod
        def configure_successful_cancelation_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable]) -> str:
            """
            :return: the URL configured for the cancelation
            """
            raise NotImplementedError

        @abstractmethod
        def configure_erroneous_cancelation_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable]) -> str:
            """
            :return: the URL configured for the cancelation
            """
            raise NotImplementedError

        @abstractmethod
        def configure_one_successful_one_erroneous_cancel_all_response(
                self,
                successful_order: InFlightOrder,
                erroneous_order: InFlightOrder,
                mock_api: aioresponses) -> List[str]:
            """
            :return: a list of all configured URLs for the cancelations
            """

        @abstractmethod
        def configure_completely_filled_order_status_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable]) -> str:
            """
            :return: the URL configured
            """
            raise NotImplementedError

        @abstractmethod
        def configure_canceled_order_status_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable]) -> str:
            """
            :return: the URL configured
            """
            raise NotImplementedError

        @abstractmethod
        def configure_open_order_status_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable]) -> str:
            """
            :return: the URL configured
            """
            raise NotImplementedError

        @abstractmethod
        def configure_http_error_order_status_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable]) -> str:
            """
            :return: the URL configured
            """
            raise NotImplementedError

        @abstractmethod
        def configure_partially_filled_order_status_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable]) -> str:
            """
            :return: the URL configured
            """
            raise NotImplementedError

        @abstractmethod
        def configure_partial_fill_trade_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable]) -> str:
            """
            :return: the URL configured
            """
            raise NotImplementedError

        @abstractmethod
        def configure_erroneous_http_fill_trade_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable]) -> str:
            """
            :return: the URL configured
            """
            raise NotImplementedError

        @abstractmethod
        def configure_full_fill_trade_response(
                self,
                order: InFlightOrder,
                mock_api: aioresponses,
                callback: Optional[Callable]) -> str:
            """
            :return: the URL configured
            """
            raise NotImplementedError

        @abstractmethod
        def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
            raise NotImplementedError

        @abstractmethod
        def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
            raise NotImplementedError

        @abstractmethod
        def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
            raise NotImplementedError

        @abstractmethod
        def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
            raise NotImplementedError

        @classmethod
        def setUpClass(cls) -> None:
            super().setUpClass()
            cls.base_asset = "COINALPHA"
            cls.quote_asset = "HBOT"
            cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

        def setUp(self) -> None:
            super().setUp()

            self.log_records = []
            self.async_tasks: List[asyncio.Task] = []

            self.exchange = self.create_exchange_instance()

            self.exchange.logger().setLevel(1)
            self.exchange.logger().addHandler(self)
            self.exchange._order_tracker.logger().setLevel(1)
            self.exchange._order_tracker.logger().addHandler(self)
            if hasattr(self.exchange, "_time_synchronizer"):
                self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
                self.exchange._time_synchronizer.logger().setLevel(1)
                self.exchange._time_synchronizer.logger().addHandler(self)

            self._initialize_event_loggers()

            self.exchange._set_trading_pair_symbol_map(
                bidict({self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset): self.trading_pair}))

        def tearDown(self) -> None:
            for task in self.async_tasks:
                task.cancel()
            super().tearDown()

        def handle(self, record):
            self.log_records.append(record)

        def is_logged(self, log_level: str, message: str) -> bool:
            return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

        def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
            ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
            return ret

        def _initialize_event_loggers(self):
            self.buy_order_completed_logger = EventLogger()
            self.buy_order_created_logger = EventLogger()
            self.order_cancelled_logger = EventLogger()
            self.order_failure_logger = EventLogger()
            self.order_filled_logger = EventLogger()
            self.sell_order_completed_logger = EventLogger()
            self.sell_order_created_logger = EventLogger()

            events_and_loggers = [
                (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
                (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
                (MarketEvent.OrderCancelled, self.order_cancelled_logger),
                (MarketEvent.OrderFailure, self.order_failure_logger),
                (MarketEvent.OrderFilled, self.order_filled_logger),
                (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
                (MarketEvent.SellOrderCreated, self.sell_order_created_logger)]

            for event, logger in events_and_loggers:
                self.exchange.add_listener(event, logger)

        def test_supported_order_types(self):
            supported_types = self.exchange.supported_order_types()
            self.assertEqual(self.expected_supported_order_types, supported_types)

        def test_restore_tracking_states_only_registers_open_orders(self):
            orders = []
            orders.append(InFlightOrder(
                client_order_id="OID1",
                exchange_order_id="EOID1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("1000.0"),
                price=Decimal("1.0"),
                creation_timestamp=1640001112.223,
            ))
            orders.append(InFlightOrder(
                client_order_id="OID2",
                exchange_order_id="EOID2",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("1000.0"),
                price=Decimal("1.0"),
                creation_timestamp=1640001112.223,
                initial_state=OrderState.CANCELED
            ))
            orders.append(InFlightOrder(
                client_order_id="OID3",
                exchange_order_id="EOID3",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("1000.0"),
                price=Decimal("1.0"),
                creation_timestamp=1640001112.223,
                initial_state=OrderState.FILLED
            ))
            orders.append(InFlightOrder(
                client_order_id="OID4",
                exchange_order_id="EOID4",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("1000.0"),
                price=Decimal("1.0"),
                creation_timestamp=1640001112.223,
                initial_state=OrderState.FAILED
            ))

            tracking_states = {order.client_order_id: order.to_json() for order in orders}

            self.exchange.restore_tracking_states(tracking_states)

            self.assertIn("OID1", self.exchange.in_flight_orders)
            self.assertNotIn("OID2", self.exchange.in_flight_orders)
            self.assertNotIn("OID3", self.exchange.in_flight_orders)
            self.assertNotIn("OID4", self.exchange.in_flight_orders)

        @aioresponses()
        def test_all_trading_pairs(self, mock_api):
            self.exchange._set_trading_pair_symbol_map(None)
            url = self.all_symbols_url

            response = self.all_symbols_request_mock_response
            mock_api.get(url, body=json.dumps(response))

            all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

            self.assertEqual(1, len(all_trading_pairs))
            self.assertIn(self.trading_pair, all_trading_pairs)

        @aioresponses()
        def test_invalid_trading_pair_not_in_all_trading_pairs(self, mock_api):
            self.exchange._set_trading_pair_symbol_map(None)
            url = self.all_symbols_url

            invalid_pair, response = self.all_symbols_including_invalid_pair_mock_response
            mock_api.get(url, body=json.dumps(response))

            all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

            self.assertNotIn(invalid_pair, all_trading_pairs)

        @aioresponses()
        def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
            self.exchange._set_trading_pair_symbol_map(None)

            url = self.all_symbols_url
            mock_api.get(url, exception=Exception)

            result: List[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

            self.assertEqual(0, len(result))

        @aioresponses()
        def test_get_last_trade_prices(self, mock_api):
            url = self.latest_prices_url

            response = self.latest_prices_request_mock_response

            mock_api.get(url, body=json.dumps(response))

            latest_prices: Dict[str, float] = self.async_run_with_timeout(
                self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
            )

            self.assertEqual(1, len(latest_prices))
            self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

        @aioresponses()
        def test_check_network_success(self, mock_api):
            url = self.network_status_url
            response = self.network_status_request_successful_mock_response
            mock_api.get(url, body=json.dumps(response))

            network_status = self.async_run_with_timeout(coroutine=self.exchange.check_network())

            self.assertEqual(NetworkStatus.CONNECTED, network_status)

        @aioresponses()
        def test_check_network_failure(self, mock_api):
            url = self.network_status_url
            mock_api.get(url, status=500)

            ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

            self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

        @aioresponses()
        def test_check_network_raises_cancel_exception(self, mock_api):
            url = self.network_status_url

            mock_api.get(url, exception=asyncio.CancelledError)

            self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

        def test_initial_status_dict(self):
            self.exchange._set_trading_pair_symbol_map(None)

            status_dict = self.exchange.status_dict

            expected_initial_dict = {
                "symbols_mapping_initialized": False,
                "order_books_initialized": False,
                "account_balance": False,
                "trading_rule_initialized": False,
                "user_stream_initialized": False,
            }

            self.assertEqual(expected_initial_dict, status_dict)
            self.assertFalse(self.exchange.ready)

        @aioresponses()
        def test_update_trading_rules(self, mock_api):
            self.exchange._set_current_timestamp(1000)

            url = self.trading_rules_url
            response = self.trading_rules_request_mock_response
            mock_api.get(url, body=json.dumps(response))

            self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

            self.assertTrue(self.trading_pair in self.exchange.trading_rules)
            self.assertEqual(repr(self.expected_trading_rule), repr(self.exchange.trading_rules[self.trading_pair]))

        @aioresponses()
        def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
            self.exchange._set_current_timestamp(1000)

            url = self.trading_rules_url
            response = self.trading_rules_request_erroneous_mock_response
            mock_api.get(url, body=json.dumps(response))

            self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

            self.assertEqual(0, len(self.exchange._trading_rules))
            self.assertTrue(
                self.is_logged("ERROR", self.expected_logged_error_for_erroneous_trading_rule)
            )

        @aioresponses()
        def test_create_buy_limit_order_successfully(self, mock_api):
            self._simulate_trading_rules_initialized()
            request_sent_event = asyncio.Event()
            self.exchange._set_current_timestamp(1640780000)

            url = self.order_creation_url

            creation_response = self.order_creation_request_successful_mock_response

            mock_api.post(url,
                          body=json.dumps(creation_response),
                          callback=lambda *args, **kwargs: request_sent_event.set())

            order_id = self.exchange.buy(trading_pair=self.trading_pair,
                                         amount=Decimal("100"),
                                         order_type=OrderType.LIMIT,
                                         price=Decimal("10000"))
            self.async_run_with_timeout(request_sent_event.wait())

            order_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_request)
            self.assertIn(order_id, self.exchange.in_flight_orders)
            self.validate_order_creation_request(
                order=self.exchange.in_flight_orders[order_id],
                request_call=order_request)

            create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
            self.assertEqual(self.trading_pair, create_event.trading_pair)
            self.assertEqual(OrderType.LIMIT, create_event.type)
            self.assertEqual(Decimal("100"), create_event.amount)
            self.assertEqual(Decimal("10000"), create_event.price)
            self.assertEqual(order_id, create_event.order_id)
            self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                    f"{Decimal('100.000000')} {self.trading_pair}."
                )
            )

        @aioresponses()
        def test_create_sell_limit_order_successfully(self, mock_api):
            self._simulate_trading_rules_initialized()
            request_sent_event = asyncio.Event()
            self.exchange._set_current_timestamp(1640780000)

            url = self.order_creation_url
            creation_response = self.order_creation_request_successful_mock_response

            mock_api.post(url,
                          body=json.dumps(creation_response),
                          callback=lambda *args, **kwargs: request_sent_event.set())

            order_id = self.exchange.sell(trading_pair=self.trading_pair,
                                          amount=Decimal("100"),
                                          order_type=OrderType.LIMIT,
                                          price=Decimal("10000"))
            self.async_run_with_timeout(request_sent_event.wait())

            order_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_request)
            self.assertIn(order_id, self.exchange.in_flight_orders)
            self.validate_order_creation_request(
                order=self.exchange.in_flight_orders[order_id],
                request_call=order_request)

            create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
            self.assertEqual(self.trading_pair, create_event.trading_pair)
            self.assertEqual(OrderType.LIMIT, create_event.type)
            self.assertEqual(Decimal("100"), create_event.amount)
            self.assertEqual(Decimal("10000"), create_event.price)
            self.assertEqual(order_id, create_event.order_id)
            self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                    f"{Decimal('100.000000')} {self.trading_pair}."
                )
            )

        @aioresponses()
        def test_create_order_fails_and_raises_failure_event(self, mock_api):
            self._simulate_trading_rules_initialized()
            request_sent_event = asyncio.Event()
            self.exchange._set_current_timestamp(1640780000)
            url = self.order_creation_url
            mock_api.post(url,
                          status=400,
                          callback=lambda *args, **kwargs: request_sent_event.set())

            order_id = self.exchange.buy(
                trading_pair=self.trading_pair,
                amount=Decimal("100"),
                order_type=OrderType.LIMIT,
                price=Decimal("10000"))
            self.async_run_with_timeout(request_sent_event.wait())

            order_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_request)
            self.assertNotIn(order_id, self.exchange.in_flight_orders)
            order_to_validate_request = InFlightOrder(
                client_order_id=order_id,
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                amount=Decimal("100"),
                creation_timestamp=self.exchange.current_timestamp,
                price=Decimal("10000")
            )
            self.validate_order_creation_request(
                order=order_to_validate_request,
                request_call=order_request)

            self.assertEquals(0, len(self.buy_order_created_logger.event_log))
            failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
            self.assertEqual(OrderType.LIMIT, failure_event.order_type)
            self.assertEqual(order_id, failure_event.order_id)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                    f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                    f"client_order_id='{order_id}', exchange_order_id=None)"
                )
            )

        @aioresponses()
        def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
            self._simulate_trading_rules_initialized()
            request_sent_event = asyncio.Event()
            self.exchange._set_current_timestamp(1640780000)

            url = self.order_creation_url
            mock_api.post(url,
                          status=400,
                          callback=lambda *args, **kwargs: request_sent_event.set())

            order_id_for_invalid_order = self.exchange.buy(
                trading_pair=self.trading_pair,
                amount=Decimal("0.0001"),
                order_type=OrderType.LIMIT,
                price=Decimal("0.0000001"))
            # The second order is used only to have the event triggered and avoid using timeouts for tests
            order_id = self.exchange.buy(
                trading_pair=self.trading_pair,
                amount=Decimal("100"),
                order_type=OrderType.LIMIT,
                price=Decimal("10000"))
            self.async_run_with_timeout(request_sent_event.wait())

            self.assertNotIn(order_id_for_invalid_order, self.exchange.in_flight_orders)
            self.assertNotIn(order_id, self.exchange.in_flight_orders)

            self.assertEquals(0, len(self.buy_order_created_logger.event_log))
            failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
            self.assertEqual(OrderType.LIMIT, failure_event.order_type)
            self.assertEqual(order_id_for_invalid_order, failure_event.order_id)

            self.assertTrue(
                self.is_logged(
                    "WARNING",
                    "Buy order amount 0 is lower than the minimum order size 0.01. The order will not be created."
                )
            )
            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                    f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                    f"client_order_id='{order_id}', exchange_order_id=None)"
                )
            )

        @aioresponses()
        def test_cancel_order_successfully(self, mock_api):
            request_sent_event = asyncio.Event()
            self.exchange._set_current_timestamp(1640780000)

            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="4",
                trading_pair=self.trading_pair,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("100"),
                order_type=OrderType.LIMIT,
            )

            self.assertIn("OID1", self.exchange.in_flight_orders)
            order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

            url = self.configure_successful_cancelation_response(
                order=order,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())

            self.exchange.cancel(trading_pair=order.trading_pair, order_id=order.client_order_id)
            self.async_run_with_timeout(request_sent_event.wait())

            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(cancel_request)
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

            if self.is_cancel_request_executed_synchronously_by_server:
                self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
                self.assertTrue(order.is_cancelled)
                cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
                self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
                self.assertEqual(order.client_order_id, cancel_event.order_id)

                self.assertTrue(
                    self.is_logged(
                        "INFO",
                        f"Successfully canceled order {order.client_order_id}."
                    )
                )
            else:
                self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
                self.assertTrue(order.is_pending_cancel_confirmation)

        @aioresponses()
        def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
            request_sent_event = asyncio.Event()
            self.exchange._set_current_timestamp(1640780000)

            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="4",
                trading_pair=self.trading_pair,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("100"),
                order_type=OrderType.LIMIT,
            )

            self.assertIn("OID1", self.exchange.in_flight_orders)
            order = self.exchange.in_flight_orders["OID1"]

            url = self.configure_erroneous_cancelation_response(
                order=order,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())

            self.exchange.cancel(trading_pair=self.trading_pair, order_id="OID1")
            self.async_run_with_timeout(request_sent_event.wait())

            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(cancel_request)
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

            self.assertEquals(0, len(self.order_cancelled_logger.event_log))
            self.assertTrue(any(log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                                for log in self.log_records))

        @aioresponses()
        def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
            self.exchange._set_current_timestamp(1640780000)

            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="4",
                trading_pair=self.trading_pair,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("100"),
                order_type=OrderType.LIMIT,
            )

            self.assertIn("OID1", self.exchange.in_flight_orders)
            order1 = self.exchange.in_flight_orders["OID1"]

            self.exchange.start_tracking_order(
                order_id="OID2",
                exchange_order_id="5",
                trading_pair=self.trading_pair,
                trade_type=TradeType.SELL,
                price=Decimal("11000"),
                amount=Decimal("90"),
                order_type=OrderType.LIMIT,
            )

            self.assertIn("OID2", self.exchange.in_flight_orders)
            order2 = self.exchange.in_flight_orders["OID2"]

            urls = self.configure_one_successful_one_erroneous_cancel_all_response(
                successful_order=order1,
                erroneous_order=order2,
                mock_api=mock_api)

            cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

            for url in urls:
                cancel_request = self._all_executed_requests(mock_api, url)[0]
                self.validate_auth_credentials_present(cancel_request)

            self.assertEqual(2, len(cancellation_results))
            self.assertEqual(CancellationResult(order1.client_order_id, True), cancellation_results[0])
            self.assertEqual(CancellationResult(order2.client_order_id, False), cancellation_results[1])

            if self.is_cancel_request_executed_synchronously_by_server:
                self.assertEqual(1, len(self.order_cancelled_logger.event_log))
                cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
                self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
                self.assertEqual(order1.client_order_id, cancel_event.order_id)

                self.assertTrue(
                    self.is_logged(
                        "INFO",
                        f"Successfully canceled order {order1.client_order_id}."
                    )
                )

        @aioresponses()
        def test_update_balances(self, mock_api):
            url = self.balance_url
            response = self.balance_request_mock_response_for_base_and_quote

            mock_api.get(re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")), body=json.dumps(response))
            self.async_run_with_timeout(self.exchange._update_balances())

            available_balances = self.exchange.available_balances
            total_balances = self.exchange.get_all_balances()

            self.assertEqual(Decimal("10"), available_balances[self.base_asset])
            self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
            self.assertEqual(Decimal("15"), total_balances[self.base_asset])
            self.assertEqual(Decimal("2000"), total_balances[self.quote_asset])

            response = self.balance_request_mock_response_only_base

            mock_api.get(re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?")), body=json.dumps(response))
            self.async_run_with_timeout(self.exchange._update_balances())

            available_balances = self.exchange.available_balances
            total_balances = self.exchange.get_all_balances()

            self.assertNotIn(self.quote_asset, available_balances)
            self.assertNotIn(self.quote_asset, total_balances)
            self.assertEqual(Decimal("10"), available_balances[self.base_asset])
            self.assertEqual(Decimal("15"), total_balances[self.base_asset])

        @aioresponses()
        def test_update_order_status_when_filled(self, mock_api):
            self.exchange._set_current_timestamp(1640780000)
            request_sent_event = asyncio.Event()

            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="EOID1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("1"),
            )
            order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

            url = self.configure_completely_filled_order_status_response(
                order=order,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())

            if self.is_order_fill_http_update_included_in_status_update:
                trade_url = self.configure_full_fill_trade_response(
                    order=order,
                    mock_api=mock_api)
            else:
                # If the fill events will not be requested with the order status, we need to manually set the event
                # to allow the ClientOrderTracker to process the last status update
                order.completely_filled_event.set()
            self.async_run_with_timeout(self.exchange._update_order_status())
            # Execute one more synchronization to ensure the async task that processes the update is finished
            self.async_run_with_timeout(request_sent_event.wait())

            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

            self.async_run_with_timeout(order.wait_until_completely_filled())
            self.assertTrue(order.is_done)
            if self.is_order_fill_http_update_included_in_status_update:
                self.assertTrue(order.is_filled)

            if self.is_order_fill_http_update_included_in_status_update:
                trades_request = self._all_executed_requests(mock_api, trade_url)[0]
                self.validate_auth_credentials_present(trades_request)
                self.validate_trades_request(
                    order=order,
                    request_call=trades_request)

                fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
                self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
                self.assertEqual(order.client_order_id, fill_event.order_id)
                self.assertEqual(order.trading_pair, fill_event.trading_pair)
                self.assertEqual(order.trade_type, fill_event.trade_type)
                self.assertEqual(order.order_type, fill_event.order_type)
                self.assertEqual(order.price, fill_event.price)
                self.assertEqual(order.amount, fill_event.amount)
                self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

            buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
            self.assertEqual(order.client_order_id, buy_event.order_id)
            self.assertEqual(order.base_asset, buy_event.base_asset)
            self.assertEqual(order.quote_asset, buy_event.quote_asset)
            self.assertEqual(
                order.amount if self.is_order_fill_http_update_included_in_status_update else Decimal(0),
                buy_event.base_asset_amount)
            self.assertEqual(
                order.amount * order.price
                if self.is_order_fill_http_update_included_in_status_update
                else Decimal(0),
                buy_event.quote_asset_amount)
            self.assertEqual(order.order_type, buy_event.order_type)
            self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"BUY order {order.client_order_id} completely filled."
                )
            )

        @aioresponses()
        def test_update_order_status_when_canceled(self, mock_api):
            self.exchange._set_current_timestamp(1640780000)

            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="100234",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("1"),
            )
            order = self.exchange.in_flight_orders["OID1"]

            url = self.configure_canceled_order_status_response(
                order=order,
                mock_api=mock_api)

            self.async_run_with_timeout(self.exchange._update_order_status(), timeout=20)

            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

            cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
            self.assertEqual(order.client_order_id, cancel_event.order_id)
            self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(
                self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
            )

        @aioresponses()
        def test_update_order_status_when_order_has_not_changed(self, mock_api):
            self.exchange._set_current_timestamp(1640780000)

            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="EOID1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("1"),
            )
            order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

            url = self.configure_open_order_status_response(
                order=order,
                mock_api=mock_api)

            self.assertTrue(order.is_open)

            self.async_run_with_timeout(self.exchange._update_order_status())

            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

            self.assertTrue(order.is_open)
            self.assertFalse(order.is_filled)
            self.assertFalse(order.is_done)

        @aioresponses()
        def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
            self.exchange._set_current_timestamp(1640780000)

            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="EOID1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("1"),
            )
            order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

            url = self.configure_http_error_order_status_response(
                order=order,
                mock_api=mock_api)

            self.async_run_with_timeout(self.exchange._update_order_status())

            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

            self.assertTrue(order.is_open)
            self.assertFalse(order.is_filled)
            self.assertFalse(order.is_done)

            self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

        @aioresponses()
        def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
            self.exchange._set_current_timestamp(1640780000)

            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="EOID1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("1"),
            )
            order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

            order_url = self.configure_partially_filled_order_status_response(
                order=order,
                mock_api=mock_api)

            if self.is_order_fill_http_update_included_in_status_update:
                trade_url = self.configure_partial_fill_trade_response(
                    order=order,
                    mock_api=mock_api)

            self.assertTrue(order.is_open)

            self.async_run_with_timeout(self.exchange._update_order_status())

            order_status_request = self._all_executed_requests(mock_api, order_url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

            self.assertTrue(order.is_open)
            self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)

            if self.is_order_fill_http_update_included_in_status_update:
                trades_request = self._all_executed_requests(mock_api, trade_url)[0]
                self.validate_auth_credentials_present(trades_request)
                self.validate_trades_request(
                    order=order,
                    request_call=trades_request)

                fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
                self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
                self.assertEqual(order.client_order_id, fill_event.order_id)
                self.assertEqual(order.trading_pair, fill_event.trading_pair)
                self.assertEqual(order.trade_type, fill_event.trade_type)
                self.assertEqual(order.order_type, fill_event.order_type)
                self.assertEqual(self.expected_partial_fill_price, fill_event.price)
                self.assertEqual(self.expected_partial_fill_amount, fill_event.amount)
                self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

        @aioresponses()
        def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self, mock_api):
            self.exchange._set_current_timestamp(1640780000)

            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="EOID1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("1"),
            )
            order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

            url = self.configure_completely_filled_order_status_response(
                order=order,
                mock_api=mock_api)

            if self.is_order_fill_http_update_included_in_status_update:
                trade_url = self.configure_erroneous_http_fill_trade_response(
                    order=order,
                    mock_api=mock_api)

            # Since the trade fill update will fail we need to manually set the event
            # to allow the ClientOrderTracker to process the last status update
            order.completely_filled_event.set()
            self.async_run_with_timeout(self.exchange._update_order_status())
            # Execute one more synchronization to ensure the async task that processes the update is finished
            self.async_run_with_timeout(order.wait_until_completely_filled())

            order_status_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_status_request)
            self.validate_order_status_request(
                order=order,
                request_call=order_status_request)

            self.assertTrue(order.is_filled)
            self.assertTrue(order.is_done)

            if self.is_order_fill_http_update_included_in_status_update:
                trades_request = self._all_executed_requests(mock_api, trade_url)[0]
                self.validate_auth_credentials_present(trades_request)
                self.validate_trades_request(
                    order=order,
                    request_call=trades_request)

            self.assertEqual(0, len(self.order_filled_logger.event_log))

            buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
            self.assertEqual(order.client_order_id, buy_event.order_id)
            self.assertEqual(order.base_asset, buy_event.base_asset)
            self.assertEqual(order.quote_asset, buy_event.quote_asset)
            self.assertEqual(Decimal(0), buy_event.base_asset_amount)
            self.assertEqual(Decimal(0), buy_event.quote_asset_amount)
            self.assertEqual(order.order_type, buy_event.order_type)
            self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"BUY order {order.client_order_id} completely filled."
                )
            )

        def test_user_stream_update_for_new_order(self):
            self.exchange._set_current_timestamp(1640780000)
            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="EOID1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("1"),
            )
            order = self.exchange.in_flight_orders["OID1"]

            order_event = self.order_event_for_new_order_websocket_update(order=order)

            mock_queue = AsyncMock()
            event_messages = [order_event, asyncio.CancelledError]
            mock_queue.get.side_effect = event_messages
            self.exchange._user_stream_tracker._user_stream = mock_queue

            try:
                self.async_run_with_timeout(self.exchange._user_stream_event_listener())
            except asyncio.CancelledError:
                pass

            event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, event.timestamp)
            self.assertEqual(order.order_type, event.type)
            self.assertEqual(order.trading_pair, event.trading_pair)
            self.assertEqual(order.amount, event.amount)
            self.assertEqual(order.price, event.price)
            self.assertEqual(order.client_order_id, event.order_id)
            self.assertEqual(order.exchange_order_id, event.exchange_order_id)
            self.assertTrue(order.is_open)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Created {order.order_type.name.upper()} {order.trade_type.name.upper()} order "
                    f"{order.client_order_id} for {order.amount} {order.trading_pair}."
                )
            )

        def test_user_stream_update_for_canceled_order(self):
            self.exchange._set_current_timestamp(1640780000)
            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="EOID1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("1"),
            )
            order = self.exchange.in_flight_orders["OID1"]

            order_event = self.order_event_for_canceled_order_websocket_update(order=order)

            mock_queue = AsyncMock()
            event_messages = [order_event, asyncio.CancelledError]
            mock_queue.get.side_effect = event_messages
            self.exchange._user_stream_tracker._user_stream = mock_queue

            try:
                self.async_run_with_timeout(self.exchange._user_stream_event_listener())
            except asyncio.CancelledError:
                pass

            cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
            self.assertEqual(order.client_order_id, cancel_event.order_id)
            self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(order.is_cancelled)
            self.assertTrue(order.is_done)

            self.assertTrue(
                self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
            )

        @aioresponses()
        def test_user_stream_update_for_order_full_fill(self, mock_api):
            self.exchange._set_current_timestamp(1640780000)
            self.exchange.start_tracking_order(
                order_id="OID1",
                exchange_order_id="EOID1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("1"),
            )
            order = self.exchange.in_flight_orders["OID1"]

            order_event = self.order_event_for_full_fill_websocket_update(order=order)
            trade_event = self.trade_event_for_full_fill_websocket_update(order=order)

            mock_queue = AsyncMock()
            event_messages = []
            if trade_event:
                event_messages.append(trade_event)
            if order_event:
                event_messages.append(order_event)
            event_messages.append(asyncio.CancelledError)
            mock_queue.get.side_effect = event_messages
            self.exchange._user_stream_tracker._user_stream = mock_queue

            if self.is_order_fill_http_update_executed_during_websocket_order_event_processing:
                self.configure_full_fill_trade_response(
                    order=order,
                    mock_api=mock_api)

            try:
                self.async_run_with_timeout(self.exchange._user_stream_event_listener())
            except asyncio.CancelledError:
                pass
            # Execute one more synchronization to ensure the async task that processes the update is finished
            self.async_run_with_timeout(order.wait_until_completely_filled())

            fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(order.price, fill_event.price)
            self.assertEqual(order.amount, fill_event.amount)
            expected_fee = self.expected_fill_fee
            self.assertEqual(expected_fee, fill_event.trade_fee)

            buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
            self.assertEqual(order.client_order_id, buy_event.order_id)
            self.assertEqual(order.base_asset, buy_event.base_asset)
            self.assertEqual(order.quote_asset, buy_event.quote_asset)
            self.assertEqual(order.amount, buy_event.base_asset_amount)
            self.assertEqual(order.amount * fill_event.price, buy_event.quote_asset_amount)
            self.assertEqual(order.order_type, buy_event.order_type)
            self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(order.is_filled)
            self.assertTrue(order.is_done)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"BUY order {order.client_order_id} completely filled."
                )
            )

        def test_user_stream_balance_update(self):
            if self.exchange.real_time_balance_update:
                self.exchange._set_current_timestamp(1640780000)

                balance_event = self.balance_event_websocket_update

                mock_queue = AsyncMock()
                mock_queue.get.side_effect = [balance_event, asyncio.CancelledError]
                self.exchange._user_stream_tracker._user_stream = mock_queue

                try:
                    self.async_run_with_timeout(self.exchange._user_stream_event_listener())
                except asyncio.CancelledError:
                    pass

                self.assertEqual(Decimal("10"), self.exchange.available_balances[self.base_asset])
                self.assertEqual(Decimal("15"), self.exchange.get_balance(self.base_asset))

        def test_user_stream_raises_cancel_exception(self):
            self.exchange._set_current_timestamp(1640780000)

            mock_queue = AsyncMock()
            mock_queue.get.side_effect = asyncio.CancelledError
            self.exchange._user_stream_tracker._user_stream = mock_queue

            self.assertRaises(
                asyncio.CancelledError,
                self.async_run_with_timeout,
                self.exchange._user_stream_event_listener())

        def test_user_stream_logs_errors(self):
            self.exchange._set_current_timestamp(1640780000)

            incomplete_event = "Invalid message"

            mock_queue = AsyncMock()
            mock_queue.get.side_effect = [incomplete_event, asyncio.CancelledError]
            self.exchange._user_stream_tracker._user_stream = mock_queue

            with patch(f"{type(self.exchange).__module__}.{type(self.exchange).__qualname__}._sleep"):
                try:
                    self.async_run_with_timeout(self.exchange._user_stream_event_listener())
                except asyncio.CancelledError:
                    pass

            self.assertTrue(
                self.is_logged(
                    "ERROR",
                    "Unexpected error in user stream listener loop."
                )
            )

        def _simulate_trading_rules_initialized(self):
            self.exchange._trading_rules = {
                self.trading_pair: TradingRule(
                    trading_pair=self.trading_pair,
                    min_order_size=Decimal(str(0.01)),
                    min_price_increment=Decimal(str(0.0001)),
                    min_base_amount_increment=Decimal(str(0.000001)),
                )
            }

        def _all_executed_requests(self, api_mock: aioresponses, url: str) -> List[RequestCall]:
            request_calls = []
            for key, value in api_mock.requests.items():
                if key[1].human_repr().startswith(url):
                    request_calls.extend(value)
            return request_calls
