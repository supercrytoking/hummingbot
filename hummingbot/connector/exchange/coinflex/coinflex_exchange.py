import asyncio
import logging
import time

from decimal import Decimal
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)

from async_timeout import timeout

import hummingbot.connector.exchange.coinflex.coinflex_constants as CONSTANTS
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.coinflex import coinflex_utils
from hummingbot.connector.exchange.coinflex.coinflex_api_order_book_data_source import CoinflexAPIOrderBookDataSource
from hummingbot.connector.exchange.coinflex.coinflex_auth import CoinflexAuth
from hummingbot.connector.exchange.coinflex.coinflex_http_utils import (
    api_call_with_retries,
    build_api_factory,
    CoinflexRESTRequest,
)
from hummingbot.connector.exchange.coinflex.coinflex_order_book_tracker import CoinflexOrderBookTracker
from hummingbot.connector.exchange.coinflex.coinflex_user_stream_tracker import CoinflexUserStreamTracker
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, OrderState, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import (
    DeductedFromReturnsTradeFee,
    TradeFeeBase,
)
from hummingbot.core.event.events import (
    OrderType,
    TradeType,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.logger import HummingbotLogger

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")


class CoinflexExchange(ExchangeBase):
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES = 3

    def __init__(self,
                 coinflex_api_key: str,
                 coinflex_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain="live"
                 ):
        self._domain = domain
        self._coinflex_time_synchronizer = TimeSynchronizer()
        super().__init__()
        self._trading_required = trading_required
        self._auth = CoinflexAuth(
            api_key=coinflex_api_key,
            secret_key=coinflex_api_secret,
            time_provider=self._coinflex_time_synchronizer)
        self._api_factory = build_api_factory(auth=self._auth)
        self._rest_assistant = None
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._order_book_tracker = CoinflexOrderBookTracker(
            trading_pairs=trading_pairs,
            domain=domain,
            api_factory=self._api_factory,
            throttler=self._throttler)
        self._user_stream_tracker = CoinflexUserStreamTracker(auth=self._auth, domain=domain, throttler=self._throttler)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._trade_fees = {}  # Dict[trading_pair:str, (maker_fee_percent:Decimal, taken_fee_percent:Decimal)]
        self._last_update_trade_fees_timestamp = 0
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0
        self._last_trades_poll_coinflex_timestamp = 0
        self._order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    @property
    def name(self) -> str:
        return "coinflex"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self.in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        Returns a dictionary associating current active orders client id to their JSON representation
        """
        return {
            key: value.to_json()
            for key, value in self.in_flight_orders.items()
        }

    def _sleep_time(self, delay: int = 0):
        """
        Function created to enable patching during unit tests execution.
        """
        return delay

    @property
    def order_book_tracker(self) -> CoinflexOrderBookTracker:
        return self._order_book_tracker

    @property
    def user_stream_tracker(self) -> CoinflexUserStreamTracker:
        return self._user_stream_tracker

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        Returns a dictionary with the values of all the conditions that determine if the connector is ready to operate.
        The key of each entry is the condition name, and the value is True if condition is ready, False otherwise.
        """
        return {
            "symbols_mapping_initialized": CoinflexAPIOrderBookDataSource.trading_pair_symbol_map_ready(
                domain=self._domain),
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "user_stream_initialized": self._user_stream_tracker.data_source.last_recv_time > 0,
        }

    @property
    def ready(self) -> bool:
        """
        Returns True if the connector is ready to operate (all connections established with the exchange). If it is
        not ready it returns False.
        """
        return all(self.status_dict.values())

    @staticmethod
    def coinflex_order_type(order_type: OrderType) -> str:
        return order_type.name.upper().split("_")[0]

    @staticmethod
    def to_hb_order_type(coinflex_type: str) -> OrderType:
        return OrderType[coinflex_type]

    def supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def start_network(self):
        """
        Start all required tasks to update the status of the connector. Those tasks include:
        - The order book tracker
        - The polling loop to update the trading rules
        - The polling loop to update order status and balance status using REST API (backup for main update process)
        - The background task to process the events received through the user stream tracker (websocket connection)
        """
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        This function is executed when the connector is stopped. It perform a general cleanup and stops all background
        tasks that require the connection with the exchange to work.
        """
        # Reset timestamps and _poll_notifier for status_polling_loop
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._poll_notifier = asyncio.Event()

        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = self._user_stream_event_listener_task = None

    async def check_network(self) -> NetworkStatus:
        """
        Checks connectivity with the exchange using the API
        """
        try:
            response = await self._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.PING_PATH_URL,
            )
            if str(response["success"]).lower() == "true":
                return NetworkStatus.CONNECTED
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.NOT_CONNECTED

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        self._order_tracker.restore_tracking_states(tracking_states=saved_states)

    def tick(self, timestamp: float):
        """
        Includes the logic that has to be processed every time a new tick happens in the bot. Particularly it enables
        the execution of the status update polling loop using an event.
        """
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self.user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)

        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def get_order_book(self, trading_pair: str) -> OrderBook:
        """
        Returns the current order book for a particular market
        :param trading_pair: the pair of tokens for which the order book should be retrieved
        """
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: Optional[str],
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        """
        Starts tracking an order by adding it to the order tracker.
        :param order_id: the order identifier
        :param exchange_order_id: the identifier for the order in the exchange
        :param trading_pair: the token pair for the operation
        :param trade_type: the type of order (buy or sell)
        :param price: the price for the order
        :param amount: the amount for the order
        :order type: type of execution for the order (MARKET, LIMIT, LIMIT_MAKER)
        """
        self._order_tracker.start_tracking_order(
            InFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
            )
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order
        :param order_id: The id of the order that will not be tracked any more
        """
        self._order_tracker.stop_tracking_order(client_order_id=order_id)

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Used by quantize_order_price() in _create_order()
        Returns a price step, a minimum price increment for a given trading pair.
        :param trading_pair: the trading pair to check for market conditions
        :param price: the starting point price
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        """
        Used by quantize_order_price() in _create_order()
        Returns an order amount step, a minimum amount increment for a given trading pair.
        :param trading_pair: the trading pair to check for market conditions
        :param order_size: the starting point order price
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_base_amount_increment

    def quantize_order_amount(self, trading_pair: str, amount: Decimal, price: Decimal = s_decimal_0) -> Decimal:
        """
        Applies the trading rules to calculate the correct order amount for the market
        :param trading_pair: the token pair for which the order will be created
        :param amount: the intended amount for the order
        :param price: the intended price for the order
        :return: the quantized order amount after applying the trading rules
        """
        trading_rule = self._trading_rules[trading_pair]
        quantized_amount: Decimal = super().quantize_order_amount(trading_pair, amount)

        # Check against min_order_size and min_notional_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        if price == s_decimal_0:
            current_price: Decimal = self.get_price(trading_pair, False)
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount

        # Add 1% as a safety factor in case the prices changed while making the order.
        if notional_size < trading_rule.min_notional_size * Decimal("1.01"):
            return s_decimal_0

        return quantized_amount

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> TradeFeeBase:
        """
        Calculates the estimated fee an order would pay based on the connector configuration
        :param base_currency: the order base currency
        :param quote_currency: the order quote currency
        :param order_type: the type of order (MARKET, LIMIT, LIMIT_MAKER)
        :param order_side: if the order is for buying or selling
        :param amount: the order amount
        :param price: the order price
        :return: the estimated fee for the order
        """

        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.LIMIT,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Creates a promise to create a buy order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        new_order_id = coinflex_utils.get_new_client_order_id(is_buy=True, trading_pair=trading_pair)
        safe_ensure_future(self._create_order(TradeType.BUY, new_order_id, trading_pair, amount, order_type, price))
        return new_order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = coinflex_utils.get_new_client_order_id(is_buy=False, trading_pair=trading_pair)
        safe_ensure_future(self._create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, price))
        return order_id

    def cancel(self, trading_pair: str, order_id: str):
        """
        Creates a promise to cancel an order in the exchange
        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel
        :return: the client id of the order to cancel
        """
        safe_ensure_future(self._execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.
        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run
        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """
        incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]
        tasks = [self._execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, Exception):
                        continue
                    if isinstance(cr, dict) and "origClientOrderId" in cr:
                        client_order_id = cr.get("origClientOrderId")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with CoinFLEX. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Optional[Decimal] = Decimal("NaN")):
        """
        Creates a an order in the exchange using the parameters to configure it
        :param trade_type: the side of the order (BUY of SELL)
        :param order_id: the id that should be assigned to the order (the client id)
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        """
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        price = self.quantize_order_price(trading_pair, price)
        quantize_amount_price = Decimal("0") if price.is_nan() else price
        amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount, price=quantize_amount_price)

        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=price,
            amount=amount,
            order_type=order_type)

        if amount < trading_rule.min_order_size:
            self.logger().warning(f"{trade_type.name.title()} order amount {amount} is lower than the minimum order"
                                  f" size {trading_rule.min_order_size}. The order will not be created.")
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=int(self.current_timestamp * 1e3),
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)
            return

        order_result = None
        amount_str = f"{amount:f}"
        type_str = CoinflexExchange.coinflex_order_type(order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await CoinflexAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler)
        api_params = {"responseType": "FULL"}
        order_params = {"marketCode": symbol,
                        "side": side_str,
                        "quantity": amount_str,
                        "orderType": type_str,
                        "clientOrderId": order_id}
        if order_type is not OrderType.MARKET:
            order_params["price"] = f"{price:f}"
        if order_type is OrderType.LIMIT:
            order_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC
        elif order_type is OrderType.LIMIT_MAKER:
            order_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_MAK
        api_params["orders"] = [order_params]

        try:
            result = await self._api_request(
                method=RESTMethod.POST,
                path_url=CONSTANTS.ORDER_CREATE_PATH_URL,
                data=api_params,
                is_auth_required=True)

            order_result = result["data"][0]

            exchange_order_id = str(order_result["orderId"])

            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                update_timestamp=int(order_result["timestamp"]),
                new_state=OrderState.OPEN,
            )
            self._order_tracker.process_order_update(order_update)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error submitting {side_str} {type_str} order to CoinFLEX for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=int(self.current_timestamp * 1e3),
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)

    async def _execute_cancel(self, trading_pair: str, order_id: str):
        """
        Requests the exchange to cancel an active order
        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel
        """
        tracked_order = self._order_tracker.fetch_tracked_order(order_id)
        if tracked_order is not None:
            try:
                symbol = await CoinflexAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair,
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
                api_params = {
                    "responseType": "FULL",
                }
                cancel_params = {
                    "marketCode": symbol,
                    "clientOrderId": order_id,
                }
                api_params["orders"] = [cancel_params]
                result = await self._api_request(
                    method=RESTMethod.DELETE,
                    path_url=CONSTANTS.ORDER_CANCEL_PATH_URL,
                    data=api_params,
                    is_auth_required=True)
                cancel_result = result["data"][0]

                if cancel_result.get("status") in CONSTANTS.ORDER_CANCELLED_STATES:
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=int(self.current_timestamp * 1e3),
                        new_state=OrderState.CANCELLED,
                    )
                    self._order_tracker.process_order_update(order_update)
                return cancel_result

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(f"There was a an error when requesting cancellation of order {order_id}")
                raise

    async def _status_polling_loop(self):
        """
        Performs all required operation to keep the connector updated and synchronized with the exchange.
        It contains the backup logic to update status using API requests in case the main update source (the user stream
        data source websocket) fails.
        It also updates the time synchronizer. This is necessary because CoinFLEX require the time of the client to be
        the same as the time in the exchange.
        Executes when the _poll_notifier event is enabled by the `tick` function.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                )
                await self._update_order_status()
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from CoinFLEX. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)
            finally:
                self._poll_notifier = asyncio.Event()

    async def _trading_rules_polling_loop(self):
        """
        Updates the trading rules by requesting the latest definitions from the exchange.
        Executes regularly every 30 minutes
        """
        while True:
            try:
                await safe_gather(
                    self._update_trading_rules(),
                )
                await asyncio.sleep(30 * 60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.", exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from CoinFLEX. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        exchange_info = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL)
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "marketId": "2001000000000",
            "marketCode": "BTC-USD",
            "name": "BTC/USD",
            "referencePair": "BTC/USD",
            "base": "BTC",
            "counter": "USD",
            "type": "SPOT",
            "tickSize": "1",
            "qtyIncrement": "0.001",
            "marginCurrency": "USD",
            "contractValCurrency": "BTC",
            "upperPriceBound": "41580",
            "lowerPriceBound": "38380",
            "marketPrice": "39980",
            "markPrice": null,
            "listingDate": 1593316800000,
            "endDate": 0,
            "marketPriceLastUpdated": 1645265706110,
            "markPriceLastUpdated": 0,
        }
        """
        trading_pair_rules = exchange_info_dict.get("data", [])
        retval = []
        for rule in filter(coinflex_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await CoinflexAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                    symbol=rule.get("marketCode"),
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)

                min_order_size = Decimal(rule.get("qtyIncrement"))
                tick_size = Decimal(rule.get("tickSize"))

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=tick_size,
                                min_base_amount_increment=min_order_size))

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("table")
                if event_type == "order":
                    order_data = event_message["data"][0]
                    client_order_id = order_data.get("clientOrderId")

                    tracked_order = self.in_flight_orders.get(client_order_id)
                    if tracked_order is not None:
                        async with timeout(self._sleep_time(5)):
                            await tracked_order.get_exchange_order_id()
                        exec_amt_base = coinflex_utils.decimal_val_or_none(order_data.get("matchQuantity"))
                        if exec_amt_base:
                            fill_price = coinflex_utils.decimal_val_or_none(order_data.get("matchPrice"))
                            exec_amt_quote = exec_amt_base * fill_price if exec_amt_base and fill_price else None
                            fee_paid = coinflex_utils.decimal_val_or_none(order_data.get("fees"))
                            trade_update = TradeUpdate(
                                trading_pair=tracked_order.trading_pair,
                                trade_id=int(order_data["matchId"]),
                                client_order_id=client_order_id,
                                exchange_order_id=str(order_data["orderId"]),
                                fill_timestamp=int(order_data["timestamp"]),
                                fill_price=fill_price,
                                fill_base_amount=exec_amt_base,
                                fill_quote_amount=exec_amt_quote,
                                fee_asset=order_data.get("feeInstrumentId"),
                                fee_paid=fee_paid,
                            )
                            self._order_tracker.process_trade_update(trade_update=trade_update)
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=int(order_data["timestamp"]),
                            new_state=CONSTANTS.ORDER_STATE[order_data["status"]],
                            client_order_id=client_order_id,
                            exchange_order_id=str(order_data["orderId"]),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == "balance":
                    self._process_balance_message(event_message)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _update_order_status(self):
        # This is intended to be a backup measure to close straggler orders, in case CoinFLEX's user stream events
        # are not working.
        # The minimum poll interval for order status is 10 seconds.
        last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL

        tracked_orders: List[InFlightOrder] = list(self.in_flight_orders.values())
        if current_tick > last_tick and len(tracked_orders) > 0:

            tasks = [self._api_request(
                     method=RESTMethod.GET,
                     path_url=CONSTANTS.ORDER_PATH_URL,
                     params={
                         "symbol": await CoinflexAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
                             trading_pair=o.trading_pair,
                             domain=self._domain,
                             api_factory=self._api_factory,
                             throttler=self._throttler),
                         "origClientOrderId": o.client_order_id},
                     is_auth_required=True,
                     endpoint_api_version="v2.1") for o in tracked_orders]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id

                # If the order has already been cancelled or has failed do nothing
                if client_order_id not in self.in_flight_orders:
                    continue

                if isinstance(order_update, Exception):
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: {order_update}.",
                        app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                    )
                    self._order_not_found_records[client_order_id] = (
                        self._order_not_found_records.get(client_order_id, 0) + 1)
                    if (self._order_not_found_records[client_order_id] >=
                            self.MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES):
                        # Wait until the order not found error have repeated a few times before actually treating
                        # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601

                        order_update: OrderUpdate = OrderUpdate(
                            client_order_id=client_order_id,
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=int(self.current_timestamp * 1e3),
                            new_state=OrderState.FAILED,
                        )
                        self._order_tracker.process_order_update(order_update)

                else:
                    # Update order execution status
                    new_state = CONSTANTS.ORDER_STATE[order_update["status"]]

                    update = OrderUpdate(
                        client_order_id=client_order_id,
                        exchange_order_id=str(order_update["orderId"]),
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=int(order_update["timestamp"]),
                        new_state=new_state,
                    )
                    self._order_tracker.process_order_update(update)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from CoinFLEX. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _update_balances(self):

        try:
            account_info = await self._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.ACCOUNTS_PATH_URL,
                is_auth_required=True)

            self._process_balance_message(account_info)
        except Exception:
            self.logger().exception("Error getting account balances from server")

    def _process_balance_message(self, account_info):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        balances = account_info["data"]
        for balance_entry in balances:
            asset_name = balance_entry["instrumentId"]
            free_balance = Decimal(balance_entry["available"])
            total_balance = Decimal(balance_entry["total"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _api_request(self,
                           method: RESTMethod,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           domain_api_version: str = None,
                           endpoint_api_version: str = None) -> Dict[str, Any]:

        client = await self._get_rest_assistant()

        request = CoinflexRESTRequest(method=method,
                                      endpoint=path_url,
                                      domain=self._domain,
                                      domain_api_version=domain_api_version,
                                      endpoint_api_version=endpoint_api_version,
                                      data=data,
                                      params=params,
                                      is_auth_required=is_auth_required)

        response = await api_call_with_retries(request=request, rest_assistant=client, throttler=self._throttler, logger=self.logger())

        # if response.status != 200:
        #     data = await response.text()
        #     raise IOError(f"Error fetching data from {url}. HTTP status is {response.status} ({data}).")
        # try:
        #     parsed_response = await response.json()
        # except Exception:
        #     raise IOError(f"Error parsing data from {response}.")

        # if "code" in parsed_response and "msg" in parsed_response:
        #     raise IOError(f"The request to CoinFLEX failed. Error: {parsed_response}. Request: {request}")

        return response

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant
