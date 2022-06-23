import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.exchange.okx import okx_constants as CONSTANTS, okx_utils, okx_web_utils as web_utils
from hummingbot.connector.exchange.okx.okx_api_order_book_data_source import OkxAPIOrderBookDataSource
from hummingbot.connector.exchange.okx.okx_api_user_stream_data_source import OkxAPIUserStreamDataSource
from hummingbot.connector.exchange.okx.okx_auth import OkxAuth
from hummingbot.connector.exchange_base import s_decimal_NaN
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class OkxExchange(ExchangePyBase):

    web_utils = web_utils

    def __init__(self,
                 okx_api_key: str,
                 okx_secret_key: str,
                 okx_passphrase: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        self.okx_api_key = okx_api_key
        self.okx_secret_key = okx_secret_key
        self.okx_passphrase = okx_passphrase
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__()

    @property
    def authenticator(self):
        return OkxAuth(
            api_key=self.okx_api_key,
            secret_key=self.okx_secret_key,
            passphrase=self.okx_passphrase,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "okx"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return ""

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.CLIENT_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.OKX_INSTRUMENTS_PATH

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.OKX_INSTRUMENTS_PATH

    @property
    def check_network_request_path(self):
        return CONSTANTS.OKX_SERVER_TIME_PATH

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return OkxAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return OkxAPIUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        fee = build_trade_fee(
            self.name,
            is_maker,
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
        )
        return fee

    async def _initialize_trading_pair_symbol_map(self):
        # This has to be reimplemented because the request requires an extra parameter
        try:
            exchange_info = await self._api_get(
                path_url=self.trading_pairs_request_path,
                params={"instType": "SPOT"},
            )
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(okx_utils.is_exchange_information_valid, exchange_info["data"]):
            mapping[symbol_data["instId"]] = combine_to_hb_trading_pair(base=symbol_data["baseCcy"],
                                                                        quote=symbol_data["quoteCcy"])
        self._set_trading_pair_symbol_map(mapping)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal) -> Tuple[str, float]:
        data = {
            "clOrdId": order_id,
            "tdMode": "cash",
            "ordType": "limit",
            "side": trade_type.name.lower(),
            "instId": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "sz": str(amount),
            "px": str(price)
        }

        exchange_order_id = await self._api_request(
            path_url=CONSTANTS.OKX_PLACE_ORDER_PATH,
            method=RESTMethod.POST,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.OKX_PLACE_ORDER_PATH,
        )
        data = exchange_order_id["data"][0]
        if data["sCode"] != "0":
            raise IOError(f"Error submitting order {order_id}: {data['sMsg']}")
        return str(data["ordId"]), self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        This implementation specific function is called by _cancel, and returns True if successful
        """
        params = {
            "clOrdId": order_id,
            "instId": tracked_order.trading_pair
        }
        cancel_result = await self._api_post(
            path_url=CONSTANTS.OKX_ORDER_CANCEL_PATH,
            data=params,
            is_auth_required=True,
        )
        if cancel_result["data"][0]["sCode"] == "0":
            final_result = True
        elif cancel_result["data"][0]["sCode"] == "5140":
            # Cancelation failed because the order does not exist anymore
            final_result = True
        else:
            raise IOError(cancel_result["msg"])

        return final_result

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        params = {"instId": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)}

        resp_json = await self._api_request(
            path_url=CONSTANTS.OKX_TICKER_PATH,
            params=params,
        )

        ticker_data, *_ = resp_json["data"]
        return float(ticker_data["last"])

    async def _update_balances(self):
        msg = await self._api_request(
            path_url=CONSTANTS.OKX_BALANCE_PATH,
            is_auth_required=True)

        if msg['code'] == '0':
            balances = msg['data'][0]['details']
        else:
            raise Exception(msg['msg'])

        self._account_available_balances.clear()
        self._account_balances.clear()

        for balance in balances:
            self._update_balance_from_details(balance_details=balance)

    def _update_balance_from_details(self, balance_details: Dict[str, Any]):
        equity_text = balance_details["eq"]
        available_equity_text = balance_details["availEq"]

        if equity_text and available_equity_text:
            total = Decimal(equity_text)
            available = Decimal(available_equity_text)
        else:
            available = Decimal(balance_details["availBal"])
            total = available + Decimal(balance_details["frozenBal"])
        self._account_balances[balance_details["ccy"]] = total
        self._account_available_balances[balance_details["ccy"]] = available

    async def _update_trading_rules(self):
        # This has to be reimplemented because the request requires an extra parameter
        exchange_info = await self._api_get(
            path_url=self.trading_rules_request_path,
            params={"instType": "SPOT"},
        )
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        trading_rules = []

        for info in raw_trading_pair_info.get("data", []):
            try:
                if okx_utils.is_exchange_information_valid(exchange_info=info):
                    trading_rules.append(
                        TradingRule(
                            trading_pair=await self.trading_pair_associated_to_exchange_symbol(symbol=info["instId"]),
                            min_order_size=Decimal(info["minSz"]),
                            min_price_increment=Decimal(info["tickSz"]),
                            min_base_amount_increment=Decimal(info["lotSz"]),
                        )
                    )
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {info}. Skipping.")
        return trading_rules

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _request_order_update(self, order: InFlightOrder) -> Dict[str, Any]:
        return await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.OKX_ORDER_DETAILS_PATH,
            params={
                "instId": await self.exchange_symbol_associated_to_pair(order.trading_pair),
                "clOrdId": order.client_order_id},
            is_auth_required=True)

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        return await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.OKX_TRADE_FILLS_PATH,
            params={
                "instType": "SPOT",
                "instId": await self.exchange_symbol_associated_to_pair(order.trading_pair),
                "ordId": await order.get_exchange_order_id()},
            is_auth_required=True)

    async def _update_order_status(self):
        tracked_orders = list(self.in_flight_orders.values())
        order_tasks = []
        order_fills_tasks = []

        if tracked_orders:
            # OKX was failing randomly to do the order update because the connector was creating a rejected signature.
            # To avoid the issue we need to make sure the time synchronizer is updated before doing the requests.

            # Also we add a retry logic in case there are problems with the signature

            for retry_count in range(3):
                invalid_signature_happened = False
                try:
                    await self._update_time_synchronizer()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    pass

                for order in tracked_orders:
                    order_tasks.append(asyncio.create_task(self._request_order_update(order=order)))
                    order_fills_tasks.append(asyncio.create_task(self._request_order_fills(order=order)))
                self.logger().debug(f"Polling for order status updates of {len(order_tasks)} orders.")

                order_updates = await safe_gather(*order_tasks, return_exceptions=True)
                order_fills = await safe_gather(*order_fills_tasks, return_exceptions=True)
                for order_update, order_fill, tracked_order in zip(order_updates, order_fills, tracked_orders):
                    client_order_id = tracked_order.client_order_id

                    # If the order has already been cancelled or has failed do nothing
                    if client_order_id not in self.in_flight_orders:
                        continue

                    if isinstance(order_fill, Exception):
                        if '"code":"50113"' in str(order_fill):
                            invalid_signature_happened = True
                        else:
                            self.logger().network(
                                f"Error fetching order fills for the order {client_order_id}: {order_fill}.",
                                app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                            )

                    else:
                        fills_data = order_fill["data"]

                        for fill_data in fills_data:
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=tracked_order.trade_type,
                                percent_token=fill_data["feeCcy"],
                                flat_fees=[TokenAmount(amount=Decimal(fill_data["fee"]), token=fill_data["feeCcy"])]
                            )
                            trade_update = TradeUpdate(
                                trade_id=str(fill_data["tradeId"]),
                                client_order_id=client_order_id,
                                exchange_order_id=str(fill_data["ordId"]),
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=Decimal(fill_data["fillSz"]),
                                fill_quote_amount=Decimal(fill_data["fillSz"]) * Decimal(fill_data["fillPx"]),
                                fill_price=Decimal(fill_data["fillPx"]),
                                fill_timestamp=int(fill_data["ts"]) * 1e-3,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                    if isinstance(order_update, Exception):
                        if '"code":"50113"' in str(order_fill):
                            invalid_signature_happened = True
                        else:
                            self.logger().network(
                                f"Error fetching status update for the order {client_order_id}: {order_update}.",
                                app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                            )
                            await self._order_tracker.process_order_not_found(client_order_id)

                    else:
                        # Update order execution status
                        order_data = order_update["data"][0]
                        new_state = CONSTANTS.ORDER_STATE[order_data["state"]]

                        update = OrderUpdate(
                            client_order_id=client_order_id,
                            exchange_order_id=str(order_data["ordId"]),
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=int(order_data["uTime"]) * 1e-3,
                            new_state=new_state,
                        )
                        self._order_tracker.process_order_update(update)

                if invalid_signature_happened:
                    self._time_synchronizer.clear_time_offset_ms_samples()
                else:
                    return  # Stop retries if there were no errors

    async def _user_stream_event_listener(self):
        async for stream_message in self._iter_user_event_queue():
            try:
                args = stream_message.get("arg", {})
                channel = args.get("channel", None)

                if channel == CONSTANTS.OKX_WS_ORDERS_CHANNEL:
                    for data in stream_message.get("data", []):
                        order_status = CONSTANTS.ORDER_STATE[data["state"]]
                        tracked_order = self._order_tracker.fetch_order(client_order_id=data["clOrdId"])

                        if tracked_order is not None:
                            if order_status in [OrderState.PARTIALLY_FILLED, OrderState.FILLED]:
                                fee = TradeFeeBase.new_spot_fee(
                                    fee_schema=self.trade_fee_schema(),
                                    trade_type=tracked_order.trade_type,
                                    percent_token=data["fillFeeCcy"],
                                    flat_fees=[TokenAmount(amount=Decimal(data["fillFee"]), token=data["fillFeeCcy"])]
                                )
                                trade_update = TradeUpdate(
                                    trade_id=str(data["tradeId"]),
                                    client_order_id=tracked_order.client_order_id,
                                    exchange_order_id=str(data["ordId"]),
                                    trading_pair=tracked_order.trading_pair,
                                    fee=fee,
                                    fill_base_amount=Decimal(data["fillSz"]),
                                    fill_quote_amount=Decimal(data["fillSz"]) * Decimal(data["fillPx"]),
                                    fill_price=Decimal(data["fillPx"]),
                                    fill_timestamp=int(data["uTime"]) * 1e-3,
                                )
                                self._order_tracker.process_trade_update(trade_update)

                            order_update = OrderUpdate(
                                trading_pair=tracked_order.trading_pair,
                                update_timestamp=int(data["uTime"]) * 1e-3,
                                new_state=order_status,
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=str(data["ordId"]),
                            )
                            self._order_tracker.process_order_update(order_update=order_update)

                elif channel == CONSTANTS.OKX_WS_ACCOUNT_CHANNEL:
                    for data in stream_message.get("data", []):
                        for details in data.get("details", []):
                            self._update_balance_from_details(balance_details=details)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)
