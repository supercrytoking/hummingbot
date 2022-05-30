import asyncio
import json
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS, gate_io_web_utils as web_utils
from hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source import GateIoAPIOrderBookDataSource
from hummingbot.connector.exchange.gate_io.gate_io_api_user_stream_data_source import GateIoAPIUserStreamDataSource
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class GateIoExchange(ExchangePyBase):
    DEFAULT_DOMAIN = ""

    INTERVAL_TRADING_RULES = CONSTANTS.INTERVAL_TRADING_RULES
    # Using 120 seconds here as Gate.io websocket is quiet
    TICK_INTERVAL_LIMIT = 120.0

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

    @property
    def authenticator(self):
        return GateIoAuth(
            api_key=self._gate_io_api_key,
            secret_key=self._gate_io_secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "gate_io"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self.DEFAULT_DOMAIN

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.SYMBOL_PATH_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.NETWORK_CHECK_PATH_URL

    def supported_order_types(self):
        return [OrderType.LIMIT]

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self.domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return GateIoAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return GateIoAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            domain=self.DEFAULT_DOMAIN,
            api_factory=self._web_assistants_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
        )

    async def _format_trading_rules(self, raw_trading_pair_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.

        :param raw_trading_pair_info: The json API response
        :return A dictionary of trading rules.

        Example raw_trading_pair_info:
        https://www.gate.io/docs/apiv4/en/#list-all-currency-pairs-supported
        """
        result = []
        for rule in raw_trading_pair_info:
            try:
                if not web_utils.is_exchange_information_valid(rule):
                    continue

                trading_pair = await self._orderbook_ds.trading_pair_associated_to_exchange_symbol(rule["id"])

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
                           price: Decimal) -> Tuple[str, float]:

        order_type_str = order_type.name.lower().split("_")[0]
        symbol = await self._orderbook_ds.exchange_symbol_associated_to_pair(trading_pair)

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
        if order_result.get("status") in {"cancelled"}:
            raise web_utils.APIError({"label": "ORDER_REJECTED", "message": "Order rejected."})
        exchange_order_id = str(order_result["id"])
        return exchange_order_id, time.time()

    async def _place_cancel(self, order_id, tracked_order):
        """
        This implementation-specific method is called by _cancel
        returns True if successful
        """
        canceled = False
        exchange_order_id = await tracked_order.get_exchange_order_id()
        params = {
            'currency_pair': await self._orderbook_ds.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
        }
        resp = await self._api_delete(
            path_url=CONSTANTS.ORDER_DELETE_PATH_URL.format(order_id=exchange_order_id),
            params=params,
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_DELETE_LIMIT_ID,
        )
        canceled = resp.get("status") == "cancelled"
        return canceled

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
            raise e
        return account_info

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        orders_tasks = []
        trades_tasks = []
        reviewed_orders = []
        tracked_orders = list(self.in_flight_orders.values())

        # Prepare requests to update trades and orders
        for tracked_order in tracked_orders:
            try:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                reviewed_orders.append(tracked_order)
            except asyncio.TimeoutError:
                self.logger().network(
                    f"Skipped order status update for {tracked_order.client_order_id} "
                    "- waiting for exchange order id.")
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)
                continue

            trading_pair = await self._orderbook_ds.exchange_symbol_associated_to_pair(tracked_order.trading_pair)

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
                for trade_fills in response:
                    self._process_trade_message(trade_fills, tracked_order.client_order_id)
            else:
                self.logger().warning(
                    f"Failed to fetch trade updates for order {tracked_order.client_order_id}. "
                    f"Response: {response}")

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
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)

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
        Update fees information from the exchange
        """
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
                await self._sleep(5.0)

    def _normalise_order_message_state(self, order_msg: Dict[str, Any], tracked_order):
        state = None
        # we do not handle:
        #   "failed" because it is handled by create order
        #   "put" as the exchange order id is returned in the create order response
        #   "open" for same reason

        # same field for both WS and REST
        amount_left = Decimal(order_msg.get("left"))

        # WS
        if "event" in order_msg:
            event_type = order_msg.get("event")
            if event_type == "update":
                state = OrderState.FILLED
                if amount_left > 0:
                    state = OrderState.PARTIALLY_FILLED
            if event_type == "finish":
                state = OrderState.FILLED
                if amount_left > 0:
                    state = OrderState.CANCELED
        else:
            status = order_msg.get("status")
            if status == "closed":
                state = OrderState.FILLED
                if amount_left > 0:
                    state = OrderState.PARTIALLY_FILLED
            if status == "cancelled":
                state = OrderState.CANCELED
        return state

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancelation or failure event if needed.

        :param order_msg: The order response from either REST or web socket API (they are of the same format)

        Example Order:
        https://www.gate.io/docs/apiv4/en/#list-orders
        """
        state = None
        client_order_id = str(order_msg.get("text", ""))
        tracked_order = self.in_flight_orders.get(client_order_id, None)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return

        state = self._normalise_order_message_state(order_msg, tracked_order)
        if state:
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=int(order_msg["update_time"]),
                new_state=state,
                client_order_id=client_order_id,
                exchange_order_id=str(order_msg["id"]),
            )
            self._order_tracker.process_order_update(order_update=order_update)
            self.logger().info(f"Successfully updated order {tracked_order.client_order_id}.")

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
            fill_quote_amount=Decimal(trade["amount"]) * Decimal(trade["price"]),
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
