import logging
from decimal import Decimal
import asyncio
import aiohttp
from typing import Dict, Any
import json
import requests
import time

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.connector.balancer.balancer_in_flight_order import BalancerInFlightOrder
s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")
GATEWAY_API_URL = "http://localhost:5000"


class BalancerConnector(ConnectorBase):
    """
    BalancerConnector connects with balancer gateway APIs and provides pricing, user account tracking and trading
    functionality.
    """
    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 60.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 trading_required: bool = True
                 ):
        """
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._last_poll_timestamp = 0.0
        self._in_flight_orders = {}

    @property
    def name(self):
        return "balancer"

    def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        base, quote = trading_pair.split("-")
        side = "buy" if is_buy else "sell"
        resp = self._request_get("balancer/price", {"base": base, "quote": quote, "side": side, "amount": amount})
        if resp["price"] is not None:
            return Decimal(str(resp["price"]))

    def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        return self.get_quote_price(trading_pair, is_buy, amount)

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal):
        return self.place_order(True, trading_pair, amount, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal):
        return self.place_order(False, trading_pair, amount, price)

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal):
        side = TradeType.BUY if is_buy else TradeType.SELL
        order_id = f"{side.name.lower()}-{trading_pair}-{get_tracking_nonce()}"
        safe_ensure_future(self._create_order(side, order_id, trading_pair, amount, price))
        return order_id

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            price: Decimal):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param price: The order price
        """

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        base, quote = trading_pair.split("-")
        side = trade_type.name.lower()
        gas = Decimal("10")  # Todo: use estimate_fee for this
        api_params = {"base": base,
                      "quote": quote,
                      "amount": str(amount),
                      "side": side,
                      "maxPrice": str(price),
                      "gasPrice": str(gas),
                      }
        self.start_tracking_order(order_id, None, trading_pair, trade_type, price, amount)
        try:
            order_result = await self._api_request("get", "balancer/trade", api_params)
            hash = order_result["txHash"]["hash"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {trade_type.name} order {order_id} for {amount} {trading_pair}.")
                tracked_order.exchange_order_id = hash

            event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
            event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            self.trigger_event(event_tag, event_class(self.current_timestamp, OrderType.LIMIT, trading_pair, amount,
                                                      price, order_id))
            self.trigger_event(MarketEvent.OrderFilled,
                               OrderFilledEvent(
                                   self.current_timestamp,
                                   tracked_order.client_order_id,
                                   tracked_order.trading_pair,
                                   tracked_order.trade_type,
                                   tracked_order.order_type,
                                   price,
                                   amount,
                                   TradeFee(0.0, [("ETH", gas)]),
                                   hash
                               ))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} order to Balancer for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: str,
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = BalancerInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=OrderType.LIMIT,
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

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("1e-15")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal("1e-15")

    @property
    def ready(self):
        return all(self.status_dict.values())

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
        }

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())

    async def check_network(self) -> NetworkStatus:
        return NetworkStatus.CONNECTED

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        if time.time() - self._last_poll_timestamp > self.POLL_INTERVAL:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        resp_json = await self._api_request("get", "eth/balances")
        for token, bal in resp_json["balances"].items():
            # self._account_available_balances[token] = Decimal(str(bal))
            self._account_balances[token] = Decimal(str(bal))
            remote_asset_names.add(token)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        url = f"{GATEWAY_API_URL}/{path_url}"
        client = await self._http_client()
        if method == "get":
            if len(params) > 0:
                response = await client.get(url, params=params)
            else:
                response = await client.get(url)
        elif method == "post":
            post_json = json.dumps(params)
            response = await client.post(url, data=post_json)
        else:
            raise NotImplementedError

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        print(f"REQUEST: {method} {path_url} {params}")
        print(f"RESPONSE: {parsed_response}")
        return parsed_response

    def _request_get(self, path_url: str, params: Dict[str, Any]):
        resp = requests.get(url=f"{GATEWAY_API_URL}/{path_url}", params=params)
        return resp.json()
