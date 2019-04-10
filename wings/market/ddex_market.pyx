import aiohttp
import asyncio
from async_timeout import timeout
from collections import deque
import logging
import math
import time
from typing import (
    Dict,
    List,
    Optional
)
from decimal import Decimal
from libc.stdint cimport int64_t
from web3 import Web3
from wings.clock cimport Clock
from wings.limit_order import LimitOrder
from wings.market.market_base cimport MarketBase
from wings.market.market_base import (
    OrderType
)
from wings.wallet.web3_wallet import Web3Wallet
from wings.order_book cimport OrderBook
from wings.order_book_tracker import OrderBookTrackerDataSourceType
from wings.tracker.ddex_order_book_tracker import DDEXOrderBookTracker
from wings.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    TradeType,
    MarketTransactionFailureEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent
)
from wings.cancellation_result import CancellationResult


s_logger = None
s_decimal_0 = Decimal(0)


cdef class DDEXMarketTransactionTracker(TransactionTracker):
    cdef:
        DDEXMarket _owner

    def __init__(self, owner: DDEXMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class TradingRule:
    cdef:
        public str symbol
        public double min_order_size
        public int price_precision              # max amount of significant digits in a price
        public int price_decimals               # max amount of decimals in a price
        public int amount_decimals              # max amount of decimals in an amount
        public bint supports_limit_orders       # if limit order is allowed for this trading pair
        public bint supports_market_orders      # if market order is allowed for this trading pair

    @classmethod
    def parse_exchange_info(cls, markets: List[Dict[str, any]]) -> List[TradingRule]:
        cdef:
            list retval = []
        for market in markets:
            try:
                symbol = market["id"]
                retval.append(TradingRule(symbol,
                                          float(market["minOrderSize"]),
                                          market["pricePrecision"],
                                          market["priceDecimals"],
                                          market["amountDecimals"],
                                          "limit" in market["supportedOrderTypes"],
                                          "market" in market["supportedOrderTypes"]))
            except Exception:
                DDEXMarket.logger().error(f"Error parsing the symbol {symbol}. Skipping.", exc_info=True)
        return retval

    def __init__(self, symbol: str, min_order_size: float, price_precision: int, price_decimals: int,
                 amount_decimals: int, supports_limit_orders: bool, supports_market_orders: bool):
        self.symbol = symbol
        self.min_order_size = min_order_size
        self.price_precision = price_precision
        self.price_decimals = price_decimals
        self.amount_decimals = amount_decimals
        self.supports_limit_orders = supports_limit_orders
        self.supports_market_orders = supports_market_orders

    def __repr__(self) -> str:
        return f"TradingRule(symbol='{self.symbol}', min_order_size={self.min_order_size}, " \
               f"price_precision={self.price_precision}, price_decimals={self.price_decimals}, "\
               f"amount_decimals={self.amount_decimals}, supports_limit_orders={self.supports_limit_orders}, " \
               f"supports_market_orders={self.supports_market_orders}"

cdef class InFlightOrder:
    cdef:
        public str client_order_id
        public str exchange_order_id
        public str symbol
        public bint is_buy
        public object order_type
        public object amount
        public object price
        public object executed_amount
        public object available_amount
        public object quote_asset_amount
        public object gas_fee_amount
        public str last_state
        public object exchange_order_id_update_event

    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 symbol: str,
                 is_buy: bool,
                 order_type: OrderType,
                 amount: Decimal,
                 price: Decimal):
        self.client_order_id = client_order_id
        self.exchange_order_id = exchange_order_id
        self.symbol = symbol
        self.is_buy = is_buy
        self.order_type = order_type
        self.amount = amount
        self.available_amount = amount
        self.price = price
        self.executed_amount = s_decimal_0
        self.quote_asset_amount = s_decimal_0
        self.gas_fee_amount = s_decimal_0
        self.last_state = "NEW"
        self.exchange_order_id_update_event = asyncio.Event()

    def __repr__(self) -> str:
        return f"InFlightOrder(client_order_id='{self.client_order_id}', exchange_order_id='{self.exchange_order_id}', " \
               f"symbol='{self.symbol}', is_buy={self.is_buy}, order_type={self.order_type}, amount={self.amount}, " \
               f"price={self.price}, executed_amount={self.executed_amount}, available_amount={self.available_amount}, " \
               f"quote_asset_amount={self.quote_asset_amount}, gas_fee_amount={self.gas_fee_amount}, " \
               f"last_state='{self.last_state}')"

    @property
    def is_done(self) -> bool:
        return self.available_amount == s_decimal_0

    @property
    def is_cancelled(self) -> bool:
        return self.last_state in {"canceled"}

    @property
    def base_asset(self) -> str:
        return self.symbol.split('-')[0]

    @property
    def quote_asset(self) -> str:
        return self.symbol.split('-')[1]

    def update_exchange_order_id(self, exchange_id: str):
        self.exchange_order_id = exchange_id
        self.exchange_order_id_update_event.set()

    async def get_exchange_order_id(self):
        if self.exchange_order_id is None:
            await self.exchange_order_id_update_event.wait()
        return self.exchange_order_id

    def to_limit_order(self) -> LimitOrder:
        cdef:
            str base_currency
            str quote_currency

        base_currency, quote_currency = self.symbol.split("-")
        return LimitOrder(
            self.client_order_id,
            self.symbol,
            self.is_buy,
            base_currency,
            quote_currency,
            Decimal(self.price),
            Decimal(self.amount)
        )


ZERO_EX_MAINNET_PROXY = "0x74622073a4821dbfd046E9AA2ccF691341A076e1"


cdef class DDEXMarket(MarketBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    API_CALL_TIMEOUT = 10.0
    DDEX_REST_ENDPOINT = "https://api.ddex.io/v3"

    ORDER_EXPIRY_TIME = 3600.0

    @classmethod
    def logger(cls) -> logging.Logger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 wallet: Web3Wallet,
                 web3_url: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                    OrderBookTrackerDataSourceType.LOCAL_CLUSTER,
                 wallet_spender_address: str = ZERO_EX_MAINNET_PROXY,
                 symbols: Optional[List[str]] = None):
        super().__init__()
        self._order_book_tracker = DDEXOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                        symbols=symbols)
        self._account_balances = {}
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_update_order_timestamp = 0
        self._last_update_trading_rules_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._order_expiry_queue = deque()
        self._tx_tracker = DDEXMarketTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(web3_url))
        self._withdraw_rules = {}
        self._trading_rules = {}
        self._pending_approval_tx_hashes = set()
        self._status_polling_task = None
        self._order_tracker_task = None
        self._approval_tx_polling_task = None
        self._wallet = wallet
        self._wallet_spender_address = wallet_spender_address
        self._shared_client = None

    @property
    def ready(self) -> bool:
        return len(self._account_balances) > 0 \
               and len(self._trading_rules) > 0 \
               and len(self._order_book_tracker.order_books) > 0 \
               and len(self._pending_approval_tx_hashes) == 0

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def wallet(self) -> Web3Wallet:
        return self._wallet

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        cdef:
            list retval = []
            InFlightOrder typed_in_flight_order

        for in_flight_order in self._in_flight_orders.values():
            typed_in_flight_order = in_flight_order
            if ((typed_in_flight_order.order_type is not OrderType.LIMIT) or
                    typed_in_flight_order.is_done):
                continue
            retval.append(typed_in_flight_order.to_limit_order())

        return retval

    @property
    def expiring_orders(self) -> List[LimitOrder]:
        return [self._in_flight_orders[order_id].to_limit_order()
                for _, order_id
                in self._order_expiry_queue]

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                self._update_balances()
                await asyncio.gather(
                    self._update_trading_rules(),
                    self._update_order_status())
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error while fetching account updates.", exc_info=True)

    def _update_balances(self):
        self._account_balances = self.wallet.get_all_balances()

    async def _update_trading_rules(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_trading_rules_timestamp > 60.0 or len(self._trading_rules) < 1:
            markets = await self.list_market()
            trading_rules_list = TradingRule.parse_exchange_info(markets)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule
            self._last_update_trading_rules_timestamp = current_timestamp

    async def _update_order_status(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if not (current_timestamp - self._last_update_order_timestamp > 10.0 and len(self._in_flight_orders) > 0):
            return

        tracked_orders = list(self._in_flight_orders.values())
        tasks = [self.get_order(o.exchange_order_id)
                 for o in (o for o in tracked_orders if o.exchange_order_id is not None)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for order_update, tracked_order in zip(results, tracked_orders):
            if isinstance(order_update, Exception):
                self.logger().error(f"Error fetching status update for the order {tracked_order.client_order_id}: "
                                    f"{order_update}.")
                continue

            # Calculate the newly executed amount for this update.
            previous_is_done = tracked_order.is_done
            new_confirmed_amount = float(order_update["confirmedAmount"])
            execute_amount_diff = new_confirmed_amount - float(tracked_order.executed_amount)
            execute_price = float(order_update["averagePrice"])

            client_order_id = tracked_order.client_order_id
            order_type_description = (("market" if tracked_order.order_type == OrderType.MARKET else "limit") +
                                      " " +
                                      ("buy" if tracked_order.is_buy else "sell"))

            # Emit event if executed amount is greater than 0.
            if execute_amount_diff > 0:
                order_filled_event = OrderFilledEvent(
                    self._current_timestamp,
                    tracked_order.client_order_id,
                    tracked_order.symbol,
                    TradeType.BUY if tracked_order.is_buy else TradeType.SELL,
                    OrderType.MARKET if tracked_order.order_type == OrderType.MARKET else OrderType.LIMIT,
                    execute_price,
                    execute_amount_diff
                )
                self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                   f"{order_type_description} order {client_order_id}.")
                self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

            # Update the tracked order
            tracked_order.last_state = order_update["status"]
            tracked_order.executed_amount = Decimal(order_update["confirmedAmount"])
            tracked_order.available_amount = Decimal(order_update["availableAmount"])
            tracked_order.quote_asset_amount = tracked_order.executed_amount * Decimal(order_update["price"])
            tracked_order.gas_fee_amount = Decimal(order_update["gasFeeAmount"])
            if not previous_is_done and tracked_order.is_done:
                if not tracked_order.is_cancelled:
                    if tracked_order.is_buy:
                        self.logger().info(f"The {order_type_description} order {client_order_id} has "
                                           f"completed according to order status API.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    tracked_order.quote_asset,
                                                                    float(tracked_order.executed_amount),
                                                                    float(tracked_order.quote_asset_amount),
                                                                    float(tracked_order.gas_fee_amount)))
                    else:
                        self.logger().info(f"The {order_type_description} order {client_order_id} has "
                                           f"completed according to order status API.")
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(self._current_timestamp,
                                                                     tracked_order.client_order_id,
                                                                     tracked_order.base_asset,
                                                                     tracked_order.quote_asset,
                                                                     tracked_order.quote_asset,
                                                                     float(tracked_order.executed_amount),
                                                                     float(tracked_order.quote_asset_amount),
                                                                     float(tracked_order.gas_fee_amount)))
                else:
                    self.logger().info(f"The {order_type_description} order {client_order_id} has been cancelled.")
                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, client_order_id))
                self.c_expire_order(tracked_order.client_order_id)

        self._last_update_order_timestamp = current_timestamp

    async def _approval_tx_polling_loop(self):
        while len(self._pending_approval_tx_hashes) > 0:
            try:
                if len(self._pending_approval_tx_hashes) > 0:
                    for tx_hash in list(self._pending_approval_tx_hashes):
                        receipt = self._w3.eth.getTransactionReceipt(tx_hash)
                        if receipt is not None:
                            self._pending_approval_tx_hashes.remove(tx_hash)
            except Exception:
                self.logger().error("Unexpected error while fetching approval transactions.", exc_info=True)
            finally:
                await asyncio.sleep(1.0)

    def _generate_auth_headers(self) -> Dict:
        message = "HYDRO-AUTHENTICATION@%s" % (int(time.time() * 1000),)
        signature = self.wallet.current_backend.sign_hash(text=message)
        auth = "%s#%s#%s" % (self.wallet.address.lower(), message, signature)
        headers = {"Hydro-Authentication": auth}
        return headers

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           http_method: str,
                           url: str,
                           data: Optional[Dict[str, any]] = None,
                           headers: Optional[Dict[str, str]] = None) -> Dict[str, any]:
        client = await self._http_client()
        async with client.request(http_method, url=url, timeout=self.API_CALL_TIMEOUT, data=data,
                                  headers=headers) as response:
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
            data = await response.json()
            if data["status"] is not 0:
                raise IOError(f"Request to {url} has failed", data)
            self.logger().debug(f"{data}")
            return data

    async def build_unsigned_order(self, amount: str, price: str, side: str, symbol: str, order_type: OrderType,
                                   expires: int) -> Dict[str, any]:
        url = "%s/orders/build" % (self.DDEX_REST_ENDPOINT,)
        headers = self._generate_auth_headers()
        data = {
            "amount": amount,
            "price": price if price != "nan" else 0,
            "side": side,
            "marketId": symbol,
            "orderType": "market" if order_type is OrderType.MARKET else "limit",
            "expires": expires
        }

        response_data = await self._api_request('post', url=url, data=data, headers=headers)
        return response_data["data"]["order"]

    async def place_order(self, amount: str, price: str, side: str, symbol: str, order_type: OrderType,
                          expires: int = 0) -> Dict[str, any]:
        unsigned_order = await self.build_unsigned_order(symbol=symbol, amount=amount, price=price, side=side,
                                                         order_type=order_type, expires=expires)
        order_id = unsigned_order["id"]
        signature = self.wallet.current_backend.sign_hash(hexstr=order_id)

        url = "%s/orders" % (self.DDEX_REST_ENDPOINT,)
        data = {"orderId": order_id, "signature": signature}

        response_data = await self._api_request('post', url=url, data=data, headers=self._generate_auth_headers())
        return response_data["data"]["order"]

    async def cancel_order(self, client_order_id: str) -> Dict[str, any]:
        order = self.in_flight_orders.get(client_order_id)
        if not order:
            self.logger().info(f"Failed to cancel order {client_order_id}. Order not found in tracked orders.")
            return
        exchange_order_id = await order.get_exchange_order_id()
        url = "%s/orders/%s" % (self.DDEX_REST_ENDPOINT, exchange_order_id)
        response_data = await self._api_request('delete', url=url, headers=self._generate_auth_headers())
        if isinstance(response_data, dict) and response_data.get("desc") == "success":
            self.logger().info(f"Successfully cancelled order {exchange_order_id}.")
            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, client_order_id))
        response_data["client_order_id"] = client_order_id
        return response_data

    async def list_orders(self) -> Dict[str, any]:
        url = "%s/orders?status=all" % (self.DDEX_REST_ENDPOINT,)
        response_data = await self._api_request('get', url=url, headers=self._generate_auth_headers())
        return response_data["data"]["orders"]

    async def get_order(self, order_id: str) -> Dict[str, any]:
        url = "%s/orders/%s" % (self.DDEX_REST_ENDPOINT, order_id)
        response_data = await self._api_request('get', url, headers=self._generate_auth_headers())
        return response_data["data"]["order"]

    async def list_locked_balances(self) -> Dict[str, any]:
        url = "%s/account/lockedBalances" % (self.DDEX_REST_ENDPOINT,)
        response_data = await self._api_request('get', url=url, headers=self._generate_auth_headers())
        return response_data["data"]["lockedBalances"]

    async def get_market(self, symbol: str) -> Dict[str, any]:
        url = "%s/markets/%s" % (self.DDEX_REST_ENDPOINT, symbol)
        response_data = await self._api_request('get', url=url)
        return response_data["data"]["market"]

    async def list_market(self) -> Dict[str, any]:
        url = "%s/markets" % (self.DDEX_REST_ENDPOINT,)
        response_data = await self._api_request('get', url=url)
        return response_data["data"]["markets"]

    async def get_ticker(self, symbol: str) -> Dict[str, any]:
        url = "%s/markets/%s/ticker" % (self.DDEX_REST_ENDPOINT, symbol)
        response_data = await self._api_request('get', url=url)
        return response_data["data"]["ticker"]

    cdef str c_buy(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0,
                   dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"buy-{symbol}-{tracking_nonce}")

        asyncio.ensure_future(self.execute_buy(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_buy(self, order_id: str, symbol: str, amount: float, order_type: OrderType, price: float) -> str:
        cdef:
            str q_price = str(self.c_quantize_order_price(symbol, price))
            str q_amt = str(self.c_quantize_order_amount(symbol, amount))
            TradingRule trading_rule = self._trading_rules[symbol]

        try:
            if float(q_amt) < trading_rule.min_order_size:
                raise ValueError(f"Buy order amount {amount} is lower than the minimum order size ")
            if order_type is OrderType.LIMIT and trading_rule.supports_limit_orders is False:
                raise ValueError(f"Limit order is not supported for trading pair {symbol}")
            if order_type is OrderType.MARKET and trading_rule.supports_market_orders is False:
                raise ValueError(f"Market order is not supported for trading pair {symbol}")

            self.c_start_tracking_order(order_id, symbol, True, order_type, Decimal(q_amt), Decimal(q_price))
            order_result = await self.place_order(amount=q_amt, price=q_price, side="buy", symbol=symbol,
                                                  order_type=order_type)
            exchange_order_id = order_result["id"]
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     Decimal(q_amt),
                                     Decimal(q_price),
                                     order_id
                                 ))
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {exchange_order_id} for "
                                   f"{q_amt} {symbol}.")
                tracked_order.update_exchange_order_id(exchange_order_id)
            return order_id
        except Exception:
            self.c_stop_tracking_order(order_id)
            self.logger().error(f"Error submitting buy order to DDEX for {amount} {symbol}.", exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, order_id))

    cdef str c_sell(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0,
                    dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")

        asyncio.ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_sell(self, order_id: str, symbol: str, amount: float, order_type: OrderType, price: float) -> str:
        cdef:
            str q_price = str(self.c_quantize_order_price(symbol, price))
            str q_amt = str(self.c_quantize_order_amount(symbol, amount))
            TradingRule trading_rule = self._trading_rules[symbol]

        try:
            if float(q_amt) < trading_rule.min_order_size:
                raise ValueError(f"Sell order amount {amount} is lower than the minimum order size ")
            if order_type is OrderType.LIMIT and trading_rule.supports_limit_orders is False:
                raise ValueError(f"Limit order is not supported for trading pair {symbol}")
            if order_type is OrderType.MARKET and trading_rule.supports_market_orders is False:
                raise ValueError(f"Market order is not supported for trading pair {symbol}")

            self.c_start_tracking_order(order_id, symbol, False, order_type, Decimal(q_amt), Decimal(q_price))
            order_result = await self.place_order(amount=q_amt, price=q_price, side="sell", symbol=symbol,
                                                  order_type=order_type)
            exchange_order_id = order_result["id"]
            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     Decimal(q_amt),
                                     Decimal(q_price),
                                     order_id
                                 ))
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {exchange_order_id} for "
                                   f"{q_amt} {symbol}.")
                tracked_order.update_exchange_order_id(exchange_order_id)
            return order_id
        except Exception:
            self.c_stop_tracking_order(order_id)
            self.logger().error(f"Error submitting sell order to DDEX for {amount} {symbol}.", exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, order_id))

    cdef c_cancel(self, str symbol, str client_order_id):
        asyncio.ensure_future(self.cancel_order(client_order_id))

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]
        tasks = [self.cancel_order(o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await asyncio.gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, Exception):
                        continue
                    if isinstance(cr, dict) and cr.get("status") == 0:
                        client_order_id = cr.get("client_order_id")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().error(f"Unexpected error cancelling orders.", exc_info=True)

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances.copy()

    def get_balance(self, currency: str) -> float:
        return self.c_get_balance(currency)

    def get_price(self, symbol: str, is_buy: bool) -> float:
        return self.c_get_price(symbol, is_buy)

    def wrap_eth(self, amount: float) -> str:
        return self._wallet.wrap_eth(amount)

    def unwrap_eth(self, amount: float) -> str:
        return self._wallet.unwrap_eth(amount)

    cdef double c_get_balance(self, str currency) except? -1:
        return float(self._account_balances.get(currency, 0.0))

    cdef OrderBook c_get_order_book(self, str symbol):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if symbol not in order_books:
            raise ValueError(f"No order book exists for '{symbol}'.")
        return order_books[symbol]

    cdef double c_get_price(self, str symbol, bint is_buy) except? -1:
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)

        return order_book.c_get_price(is_buy)

    cdef c_start(self, Clock clock, double timestamp):
        MarketBase.c_start(self, clock, timestamp)
        self._order_tracker_task = asyncio.ensure_future(self._order_book_tracker.start())
        self._status_polling_task = asyncio.ensure_future(self._status_polling_loop())
        tx_hashes = self.wallet.current_backend.check_and_fix_approval_amounts(
            spender=self._wallet_spender_address)
        self._pending_approval_tx_hashes.update(tx_hashes)
        self._approval_tx_polling_task = asyncio.ensure_future(self._approval_tx_polling_loop())

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)

        self._tx_tracker.c_tick(timestamp)
        MarketBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self.c_check_and_remove_expired_orders()
        self._last_timestamp = timestamp

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str symbol,
                                bint is_buy,
                                object order_type,
                                object amount,
                                object price):
        self._in_flight_orders[client_order_id] = InFlightOrder(client_order_id, None, symbol, is_buy,
                                                                order_type, amount, price)

    cdef c_expire_order(self, str order_id):
        self._order_expiry_queue.append((self._current_timestamp + self.ORDER_EXPIRY_TIME, order_id))

    cdef c_check_and_remove_expired_orders(self):
        cdef:
            double current_timestamp = self._current_timestamp
            str order_id

        while len(self._order_expiry_queue) > 0 and self._order_expiry_queue[0][0] < current_timestamp:
            _, order_id = self._order_expiry_queue.popleft()
            self.c_stop_tracking_order(order_id)

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str symbol, double price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        decimals_quantum = Decimal(f"1e-{trading_rule.price_decimals}")
        if price > 0:
            precision_quantum = Decimal(f"1e{math.ceil(math.log10(price)) - trading_rule.price_precision}")
        else:
            precision_quantum = s_decimal_0
        return max(decimals_quantum, precision_quantum)

    cdef object c_get_order_size_quantum(self, str symbol, double amount):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        decimals_quantum = Decimal(f"1e-{trading_rule.amount_decimals}")
        return decimals_quantum

    cdef object c_quantize_order_amount(self, str symbol, double amount):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]

        global s_decimal_0
        quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, amount)

        # Check against min_order_size and. If not passing the check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        return quantized_amount