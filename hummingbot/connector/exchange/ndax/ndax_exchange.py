import aiohttp
import asyncio
import logging
import math
import time
import ujson

from decimal import Decimal
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
    Union,
)

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS
from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.connector.exchange.ndax.ndax_in_flight_order import NdaxInFlightOrder
from hummingbot.connector.exchange.ndax.ndax_order_book_tracker import NdaxOrderBookTracker
from hummingbot.connector.exchange.ndax.ndax_user_stream_tracker import NdaxUserStreamTracker
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.order_book import OrderBook

from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    TradeFee,
    TradeType,
)
from hummingbot.core.network_base import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger

s_decimal_NaN = Decimal("nan")


class NdaxExchange(ExchangeBase):
    """
    Class to onnect with NDAX exchange. Provides order book pricing, user account tracking and
    trading functionality.
    """
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 ndax_uid: str,
                 ndax_api_key: str,
                 ndax_secret_key: str,
                 ndax_username: str,
                 account_id: int = None,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param ndax_uid: User ID of the account
        :param ndax_api_key: The API key to connect to private NDAX APIs.
        :param ndax_secret_key: The API secret.
        :param ndax_username: The username of the account in use.
        :param account_id: The account ID associated with the trading account in use.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._auth = NdaxAuth(uid=ndax_uid, api_key=ndax_api_key, secret_key=ndax_secret_key, username=ndax_username)
        self._order_book_tracker = NdaxOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = NdaxUserStreamTracker(self._auth)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}
        # self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        # self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._last_poll_timestamp = 0

        self._status_polling_task = None
        # self._user_stream_tracker_task = None
        # self._user_stream_event_listener_task = None
        # self._trading_rules_polling_task = None

        self._account_id = account_id

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def account_id(self) -> int:
        return self._account_id

    @property
    def in_flight_orders(self) -> Dict[str, NdaxInFlightOrder]:
        return self._in_flight_orders

    def supported_order_types(self) -> List[OrderType]:
        """
        :return: a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _get_account_id(self) -> int:
        """
        Calls REST API to retrieve Account ID
        """
        params = {
            "OMSId": 0,
            "UserId": int(self._auth.uid),
            "UserName": self._auth.username
        }

        resp: List[int] = await self._api_request(
            "GET",
            path_url=CONSTANTS.USER_ACCOUNTS_PATH_URL,
            params=params,
            is_auth_required=True,
        )

        """
        NOTE: Currently there is no way to determine which accountId the user intends to use.
              The GetUserAccountInfos endpoint doesnt seem to provide anything useful either.
              The assumption here is that the FIRST entry in the list is the accountId the user intends to use
        """
        return resp[0]

    async def start_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        It starts tracking order book, polling trading rules,
        updating statuses and tracking user data.
        """
        self._order_book_tracker.start()
        # self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            if not self._account_id:
                self._account_id = await self._get_account_id()
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        """
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None

    async def check_network(self) -> NetworkStatus:
        """
        This function is required by NetworkIterator base class and is called periodically to check
        the network connection. Simply ping the network (or call any light weight public API).
        """
        try:
            resp = await self._api_request(
                method="GET",
                path_url=CONSTANTS.WS_PING_REQUEST
            )
            if "msg" not in resp or resp["msg"] != "PONG":
                raise Exception()
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False) -> Union[Dict[str, Any], List[Any]]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: The query parameters of the API request
        :param params: The body parameters of the API request
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        url = CONSTANTS.REST_URL + path_url
        client = await self._http_client()

        try:
            if is_auth_required:
                headers = self._auth.get_auth_headers()
            else:
                headers = self._auth.get_headers()

            if method == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = await client.post(url, headers=headers, data=ujson.dumps(data))
            else:
                raise NotImplementedError(f"{method} HTTP Method not implemented. ")

            parsed_response = await response.json()
        except ValueError as e:
            self.logger().error(f"{str(e)}")
            raise ValueError(f"Error authenticating request {method} {url}. Error: {str(e)}")
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response} "
                          f"Params: {params} "
                          f"Data: {data}")

        return parsed_response

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        # When the balances are requested by the client to test the connection, the account id will not be
        # initialized yet
        if not self._account_id:
            self._account_id = await self._get_account_id()

        params = {
            "OMSId": 1,
            "AccountId": self.account_id
        }
        account_positions: List[Dict[str, Any]] = await self._api_request(
            method="GET",
            path_url=CONSTANTS.ACCOUNT_POSITION_PATH_URL,
            params=params,
            is_auth_required=True
        )
        for position in account_positions:
            asset_name = position["ProductSymbol"]
            self._account_balances[asset_name] = Decimal(str(position["Amount"]))
            self._account_available_balances[asset_name] = self._account_balances[asset_name] - Decimal(
                str(position["Hold"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: str,
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = NdaxInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def _update_order_status(self):
        # Waiting on buy and sell functionality.
        pass

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for web
        socket API updates.
        """
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from NDAX. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock tick(1 second by default).
        It checks if a status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return TradeFee(percent=self.estimate_fee_pct(is_maker))

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
                    app_warning_msg="Could not fetch user events from NDAX. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                endpoint = NdaxWebSocketAdaptor.endpoint_from_message(event_message)
                payload = NdaxWebSocketAdaptor.payload_from_message(event_message)

                if endpoint == CONSTANTS.ACCOUNT_POSITION_EVENT_ENDPOINT_NAME:
                    self._process_account_position_event(payload)
                elif endpoint == CONSTANTS.ORDER_STATE_EVENT_ENDPOINT_NAME:
                    self._process_order_event_message(payload)
                elif endpoint == CONSTANTS.ORDER_TRADE_EVENT_ENDPOINT_NAME:
                    self._process_trade_event_message(payload)
                else:
                    self.logger().debug(f"Unknown event received from the connector ({event_message})")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Unexpected error in user stream listener loop ({ex})", exc_info=True)
                await asyncio.sleep(5.0)

    def _process_account_position_event(self, account_position_event: Dict[str, Any]):
        token = account_position_event["ProductSymbol"]
        amount = Decimal(str(account_position_event["Amount"]))
        on_hold = Decimal(str(account_position_event["Hold"]))
        self._account_balances[token] = amount
        self._account_available_balances[token] = (amount - on_hold)

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        client_order_id = str(order_msg["ClientOrderId"])
        if client_order_id in self.in_flight_orders:
            tracked_order = self.in_flight_orders[client_order_id]

            # Update order execution status
            tracked_order.last_state = order_msg["OrderState"]

            if tracked_order.is_cancelled:
                self.logger().info(f"Successfully cancelled order {client_order_id}")
                self.trigger_event(MarketEvent.OrderCancelled,
                                   OrderCancelledEvent(
                                       self.current_timestamp,
                                       client_order_id))
                self.stop_tracking_order(client_order_id)
            elif tracked_order.is_failure:
                self.logger().info(f"The market order {client_order_id} has failed according to order status event. "
                                   f"Reason: {order_msg['ChangeReason']}")
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(
                                       self.current_timestamp,
                                       client_order_id,
                                       tracked_order.order_type
                                   ))
                self.stop_tracking_order(client_order_id)

    def _process_trade_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        :param order_msg: The order event message payload
        """

        client_order_id = str(order_msg["ClientOrderId"])
        if client_order_id in self.in_flight_orders:
            tracked_order = self.in_flight_orders[client_order_id]
            updated = tracked_order.update_with_trade_update(order_msg)

            if updated:
                trade_amount = Decimal(str(order_msg["Quantity"]))
                trade_price = Decimal(str(order_msg["Price"]))
                trade_fee = self.get_fee(base_currency=tracked_order.base_asset,
                                         quote_currency=tracked_order.quote_asset,
                                         order_type=tracked_order.order_type,
                                         order_side=tracked_order.trade_type,
                                         amount=trade_amount,
                                         price=trade_price)
                amount_for_fee = (trade_amount if tracked_order.trade_type is TradeType.BUY
                                  else trade_amount * trade_price)
                tracked_order.fee_paid += amount_for_fee * trade_fee.percent

                self.trigger_event(
                    MarketEvent.OrderFilled,
                    OrderFilledEvent(
                        self.current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        trade_price,
                        trade_amount,
                        trade_fee,
                        exchange_trade_id=str(order_msg["TradeId"])
                    )
                )
                if (math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or
                        tracked_order.executed_amount_base >= tracked_order.amount):
                    tracked_order.mark_as_filled()
                    self.logger().info(f"The {tracked_order.trade_type.name} order "
                                       f"{tracked_order.client_order_id} has completed "
                                       f"according to order status API")
                    event_tag = (MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY
                                 else MarketEvent.SellOrderCompleted)
                    event_class = (BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY
                                   else SellOrderCompletedEvent)
                    self.trigger_event(event_tag,
                                       event_class(self.current_timestamp,
                                                   tracked_order.client_order_id,
                                                   tracked_order.base_asset,
                                                   tracked_order.quote_asset,
                                                   tracked_order.fee_asset,
                                                   tracked_order.executed_amount_base,
                                                   tracked_order.executed_amount_quote,
                                                   tracked_order.fee_paid,
                                                   tracked_order.order_type,
                                                   tracked_order.exchange_order_id))
                    self.stop_tracking_order(tracked_order.client_order_id)
