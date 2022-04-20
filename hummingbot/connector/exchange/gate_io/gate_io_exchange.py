import time
import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional
import json

from hummingbot.connector.exchange_base_v2 import ExchangeBaseV2
from hummingbot.connector.exchange.gate_io import (
    gate_io_constants as CONSTANTS,
    gate_io_web_utils as web_utils
)
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source import GateIoAPIOrderBookDataSource
from hummingbot.connector.exchange.gate_io.gate_io_api_user_stream_data_source import GateIoAPIUserStreamDataSource
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.core.event.events import (
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TradeFeeBase, TokenAmount
from hummingbot.core.data_type.in_flight_order import TradeUpdate
from hummingbot.core.utils.async_utils import safe_gather


class GateIoExchange(ExchangeBaseV2):
    DEFAULT_DOMAIN = ""
    RATE_LIMITS = CONSTANTS.RATE_LIMITS
    SUPPORTED_ORDER_TYPES = [
        OrderType.LIMIT
    ]

    HBOT_ORDER_ID_PREFIX = CONSTANTS.HBOT_ORDER_ID
    MAX_ORDER_ID_LEN = CONSTANTS.MAX_ID_LEN

    ORDERBOOK_DS_CLASS = GateIoAPIOrderBookDataSource
    USERSTREAM_DS_CLASS = GateIoAPIUserStreamDataSource

    CHECK_NETWORK_URL = CONSTANTS.NETWORK_CHECK_PATH_URL
    SYMBOLS_PATH_URL = CONSTANTS.SYMBOL_PATH_URL
    FEE_PATH_URL = SYMBOLS_PATH_URL

    INTERVAL_TRADING_RULES = CONSTANTS.INTERVAL_TRADING_RULES
    # Using 120 seconds here as Gate.io websocket is quiet
    TICK_INTERVAL_LIMIT = 10.0  # 120.0

    web_utils = web_utils

    def __init__(self,
                 gate_io_api_key: str,
                 gate_io_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = DEFAULT_DOMAIN):
        """
        :param gate_io_api_key: The API key to connect to private Gate.io APIs.
        :param gate_io_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        self._gate_io_api_key = gate_io_api_key
        self._gate_io_secret_key = gate_io_secret_key
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs

        super().__init__()

    def init_auth(self):
        return GateIoAuth(
            api_key=self._gate_io_api_key,
            secret_key=self._gate_io_secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "gate_io"

    # TODO link to example
    async def _format_trading_rules(self, raw_trading_pair_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.

        :param raw_trading_pair_info: The json API response
        :return A dictionary of trading rules.

        Response Example:
        [
            {
                "id": "ETH_USDT",
                "base": "ETH",
                "quote": "USDT",
                "fee": "0.2",
                "min_base_amount": "0.001",
                "min_quote_amount": "1.0",
                "amount_precision": 3,
                "precision": 6,
                "trade_status": "tradable",
                "sell_start": 1516378650,
                "buy_start": 1516378650
            }
        ]
        """
        result = []
        for rule in raw_trading_pair_info:
            try:
                trading_pair = web_utils.convert_from_exchange_trading_pair(rule["id"])

                min_amount_inc = Decimal(f"1e-{rule['amount_precision']}")
                min_price_inc = Decimal(f"1e-{rule['precision']}")
                min_amount = Decimal(str(rule.get("min_base_amount", min_amount_inc)))
                min_notional = Decimal(str(rule.get("min_quote_amount", min_price_inc)))
                result.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_amount,
                        min_price_increment=min_price_inc,
                        min_base_amount_increment=min_amount_inc,
                        min_notional_size=min_notional,
                        min_order_value=min_notional,
                    )
                )
            except Exception:
                self.logger().error(
                    f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return result

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal) -> str:

        order_type_str = order_type.name.lower().split("_")[0]
        symbol = web_utils.convert_to_exchange_trading_pair(trading_pair)
        data = {
            "text": order_id,
            "currency_pair": symbol,
            "side": trade_type.name.lower(),
            "type": order_type_str,
            "price": f"{price:f}",
            "amount": f"{amount:f}",
        }
        # RESTRequest does not support json, and if we pass a dict
        # the underlying aiohttp will encode it to params
        data = json.dumps(data)
        endpoint = CONSTANTS.ORDER_CREATE_PATH_URL
        order_result = await self._api_post(
            path_url=endpoint,
            data=data,
            is_auth_required=True,
            limit_id=endpoint,
        )
        if order_result.get('status') in {"cancelled", "expired", "failed"}:
            raise web_utils.APIError({'label': 'ORDER_REJECTED', 'message': 'Order rejected.'})
        exchange_order_id = str(order_result["id"])
        return exchange_order_id, time.time()

    async def _place_cancel(self, order_id, tracked_order):
        """
        This implementation-specific method is called by _cancel
        returns True if successful
        """
        cancelled = False
        exchange_order_id = await tracked_order.get_exchange_order_id()
        try:
            params = {
                'currency_pair': web_utils.convert_to_exchange_trading_pair(tracked_order.trading_pair)
            }
            resp = await self._api_delete(
                path_url=CONSTANTS.ORDER_DELETE_PATH_URL.format(order_id=exchange_order_id),
                params=params,
                is_auth_required=True,
                limit_id=CONSTANTS.ORDER_DELETE_LIMIT_ID,
            )
            if resp["status"] == "cancelled":
                cancelled = True
        except (asyncio.TimeoutError, web_utils.APIError) as e:
            self.logger().debug(f"Canceling order {order_id} failed: {e}")
        return cancelled

    async def _status_polling_loop_fetch_updates(self):
        """
        Called by _status_polling_loop, which executes after each tick() is executed
        """
        self.logger().debug(f"Running _status_polling_loop_fetch_updates() at {time.time()}")
        return await safe_gather(
            self._update_balances(),
            self._update_order_status(),
        )

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        account_info = ""
        try:
            account_info = await self._api_get(
                path_url=CONSTANTS.USER_BALANCES_PATH_URL,
                is_auth_required=True,
                limit_id=CONSTANTS.USER_BALANCES_PATH_URL
            )
            self._process_balance_message(account_info)
        except Exception as e:
            self.logger().network(
                f"Unexpected error while fetching balance update - {str(e)}", exc_info=True,
                app_warning_msg=(f"Could not fetch balance update from {self.name_cap}"))
        return account_info

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        orders_tasks = []
        trades_tasks = []
        reviewed_orders = []
        tracked_orders = list(self.in_flight_orders.values())

        print(tracked_orders)
        if len(tracked_orders) <= 0:
            return

        # Prepare requests to update trades and orders
        for tracked_order in tracked_orders:
            try:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                reviewed_orders.append(tracked_order)
            except asyncio.TimeoutError:
                self.logger().network(f"Skipped order status update for {tracked_order.client_order_id} "
                                      "- waiting for exchange order id.")
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)
                continue

            trading_pair = web_utils.convert_to_exchange_trading_pair(tracked_order.trading_pair)
            trades_tasks.append(self._api_get(
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "currency_pair": trading_pair,
                    "order_id": exchange_order_id
                },
                is_auth_required=True,
                limit_id=CONSTANTS.MY_TRADES_PATH_URL,
            ))
            orders_tasks.append(self._api_get(
                path_url=CONSTANTS.ORDER_STATUS_PATH_URL.format(order_id=exchange_order_id),
                params={
                    "currency_pair": trading_pair
                },
                is_auth_required=True,
                limit_id=CONSTANTS.ORDER_STATUS_LIMIT_ID,
            ))

        # Process order trades first before processing order statuses
        responses = await safe_gather(*trades_tasks, return_exceptions=True)
        self.logger().debug(f"Polled trade updates for {len(tracked_orders)} orders: {len(responses)}.")
        for response, tracked_order in zip(responses, reviewed_orders):
            if not isinstance(response, Exception):
                if len(response) > 0:
                    for trade_fills in response:
                        self._process_trade_message(trade_fills, tracked_order.client_order_id)
            else:
                self.logger().warning(
                    f"Failed to fetch trade updates for order {tracked_order.client_order_id}. "
                    f"Response: {response}")
                if 'ORDER_NOT_FOUND' in str(response):
                    self._order_tracker.stop_tracking_order(client_order_id=tracked_order.client_order_id)

        # Process order statuses
        responses = await safe_gather(*orders_tasks, return_exceptions=True)
        self.logger().debug(f"Polled order updates for {len(tracked_orders)} orders: {len(responses)}.")
        for response, tracked_order in zip(responses, tracked_orders):
            if not isinstance(response, Exception):
                self._process_order_message(response)
            else:
                self.logger().warning(
                    f"Failed to fetch order status updates for order {tracked_order.client_order_id}. "
                    f"Response: {response}")
                if 'ORDER_NOT_FOUND' in str(response):
                    self._order_tracker.stop_tracking_order(client_order_id=tracked_order.client_order_id)

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _update_trading_fees(self):
        """
        Initialize mapping of trade symbols in exchange notation to trade symbols in client notation
        """
        # TODO can we get fees from gate io API?
        # NOTE this same call is done by _init_trading_pair_symbols( in OB data source
        pass

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        user_channels = [
            CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            CONSTANTS.USER_BALANCE_ENDPOINT_NAME,
        ]
        async for event_message in self._iter_user_event_queue():
            channel: str = event_message.get("channel", None)
            results: str = event_message.get("result", None)
            try:
                if channel not in user_channels:
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.", exc_info=True)
                    continue

                if channel == CONSTANTS.USER_TRADES_ENDPOINT_NAME:
                    for trade_msg in results:
                        self._process_trade_message(trade_msg)
                elif channel == CONSTANTS.USER_ORDERS_ENDPOINT_NAME:
                    for order_msg in results:
                        self._process_order_message(order_msg)
                elif channel == CONSTANTS.USER_BALANCE_ENDPOINT_NAME:
                    self._process_balance_message_ws(results)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        Example Order:
        https://www.gate.io/docs/apiv4/en/#list-orders
        """
        client_order_id = str(order_msg.get("text", ""))
        tracked_order = self.in_flight_orders.get(client_order_id, None)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        state = order_msg.get("status", order_msg.get("event"))
        if state == "cancelled":
            self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id}.")
            self.trigger_event(
                MarketEvent.OrderCancelled,
                OrderCancelledEvent(self.current_timestamp, tracked_order.client_order_id))
            self.stop_tracking_order(tracked_order.client_order_id)

        # TODO is_cancelled was not working above for:
        # tracked_order.last_state = order_msg.get("status", order_msg.get("event"))
        # if tracked_order.is_cancelled:
        #
        elif tracked_order.is_failure:
            self.logger().info(f"Order {tracked_order.client_order_id} failed according to order status API. ")
            self.trigger_event(
                MarketEvent.OrderFailure,
                MarketOrderFailureEvent(self.current_timestamp, tracked_order.client_order_id, tracked_order.order_type))
            self.stop_tracking_order(tracked_order.client_order_id)

    def _process_trade_message(self, trade: Dict[str, Any], client_order_id: Optional[str] = None):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        Example Trade:
        https://www.gate.io/docs/apiv4/en/#retrieve-market-trades
        """
        client_order_id = client_order_id or str(trade["text"])
        tracked_order = self.in_flight_orders.get(client_order_id, None)
        if not tracked_order:
            self.logger().debug(f"Ignoring trade message with id {client_order_id}: not in in_flight_orders.")
            return

        # TODO review
        # {'id': '3286836540', 'create_time': '1650444945', 'create_time_ms': '1650444945003.509000',
        # 'currency_pair': 'ETH_USDT', 'side': 'buy', 'role': 'taker', 'amount': '0.001', 'price': '3100.4',
        # 'order_id': '146053117298', 'fee': '0.0000018', 'fee_currency': 'ETH', 'point_fee': '0', 'gt_fee': '0'}
        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=tracked_order.trade_type,
            percent_token=trade["fee_currency"],
            flat_fees=[TokenAmount(
                amount=Decimal(trade["fee"]),
                token=trade["fee_currency"]
            )]
        )
        trade_update = TradeUpdate(
            trade_id=str(trade["id"]),
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            fee=fee,
            fill_base_amount=Decimal(trade["amount"]),
            # TODO should this be calculated from amount * price?
            fill_quote_amount=Decimal(trade["amount"]),
            fill_price=Decimal(trade["price"]),
            fill_timestamp=trade["create_time"],
        )
        self._order_tracker.process_trade_update(trade_update)

    def _process_balance_message(self, balance_update):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        for account in balance_update:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["locked"])) + Decimal(str(account["available"]))
            remote_asset_names.add(asset_name)
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _process_balance_message_ws(self, balance_update):
        for account in balance_update:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["total"]))
