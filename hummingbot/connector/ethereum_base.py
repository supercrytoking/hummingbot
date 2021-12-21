import logging
from decimal import Decimal
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
import json
import time
import ssl
import copy
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.client.settings import GATEAWAY_CA_CERT_PATH, GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.utils.ethereum import check_transaction_exceptions, fetch_trading_pairs

s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")
logging.basicConfig(level=METRICS_LOG_LEVEL)


class EthereumBase(ConnectorBase):
    """
    Defines basic functions common to connectors that interact with Ethereum through Gateway.
    """

    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 1.0
    UPDATE_BALANCE_INTERVAL = 30.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(cls.__name__)
        return s_logger

    def __init__(self,
                 trading_pairs: List[str],
                 wallet_private_key: str,
                 trading_required: bool = True
                 ):
        """
        :param trading_pairs: a list of trading pairs
        :param wallet_private_key: a private key for eth wallet
        :param trading_required: Whether actual trading is needed. Useful for some functionalities or commands like the balance command
        """
        super().__init__()
        self._trading_pairs = trading_pairs
        self._tokens = set()
        for trading_pair in trading_pairs:
            self._tokens.update(set(trading_pair.split("-")))
        self._wallet_private_key = wallet_private_key
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._last_est_gas_cost_reported = 0
        self._in_flight_orders = {}
        self._allowances = {}
        self._chain_info = {}
        self._status_polling_task = None
        self._auto_approve_task = None
        self._get_chain_info_task = None
        self._poll_notifier = None
        self._nonce = None

    @property
    def name(self):
        raise NotImplementedError

    @property
    def base_path(self):
        raise NotImplementedError

    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        return await fetch_trading_pairs()

    @property
    def approval_orders(self) -> List[GatewayInFlightOrder]:
        return [
            approval_order
            for approval_order in self._in_flight_orders.values() if approval_order.client_order_id.split("_")[0] == "approve"
        ]

    @property
    def amm_orders(self) -> List[GatewayInFlightOrder]:
        return [
            in_flight_order
            for in_flight_order in self._in_flight_orders.values() if in_flight_order not in self.approval_orders
        ]

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self.amm_orders
        ]

    def is_pending_approval(self, token: str) -> bool:
        pending_approval_tokens = [tk.split("_")[2] for tk in self._in_flight_orders.keys()]
        return True if token in pending_approval_tokens else False

    async def get_chain_info(self):
        """
        Calls the base endpoint of the connector on Gateway to know basic info about chain being used.
        """
        try:
            resp = await self._api_request("get", f"{self.base_path}/")
            if bool(str(resp["success"])):
                self._chain_info = resp
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                "Error fetching chain info",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def auto_approve(self):
        """
        Automatically approves trading pair tokens for contract(s).
        It first checks if there are any already approved amount (allowance)
        """
        self._allowances = await self.get_allowances()
        for token, amount in self._allowances.items():
            if amount <= s_decimal_0 and not self.is_pending_approval(token):
                await self.approve_token(token)

    async def approve_token(self, token_symbol: str):
        """
        Approves contract as a spender for a token.
        :param token_symbol: token to approve.
        """
        order_id = f"approve_{self.name}_{token_symbol}"
        await self._update_nonce()
        resp = await self._api_request("post",
                                       "eth/approve",
                                       {"token": token_symbol,
                                        "spender": self.name,
                                        "nonce": self._nonce})
        self.start_tracking_order(order_id, None, token_symbol)

        if "hash" in resp.get("approval", {}).keys():
            hash = resp["approval"]["hash"]
            tracked_order = self._in_flight_orders.get(order_id)
            tracked_order.update_exchange_order_id(hash)
            self.logger().info(f"Maximum {token_symbol} approval for {self.name} contract sent, hash: {hash}.")
        else:
            self.stop_tracking_order(order_id)
            self.logger().info(f"Approval for {token_symbol} on {self.name} failed.")

    async def get_allowances(self) -> Dict[str, Decimal]:
        """
        Retrieves allowances for token in trading_pairs
        :return: A dictionary of token and its allowance.
        """
        ret_val = {}
        resp = await self._api_request("post", "eth/allowances",
                                       {"tokenSymbols": list(self._tokens),
                                        "spender": self.name})
        for token, amount in resp["approvals"].items():
            ret_val[token] = Decimal(str(amount))
        return ret_val

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Optional[Decimal]:
        """
        Retrieves a quote price.
        :param trading_pair: The market trading pair
        :param is_buy: True for an intention to buy, False for an intention to sell
        :param amount: The amount required (in base token unit)
        :return: The quote price.
        """

        try:
            base, quote = trading_pair.split("-")
            side = "buy" if is_buy else "sell"
            resp = await self._api_request("post",
                                           f"{self.base_path}/price",
                                           {"base": base,
                                            "quote": quote,
                                            "amount": str(amount),
                                            "side": side.upper()})
            required_items = ["price", "gasLimit", "gasPrice", "gasCost"]
            if any(item not in resp.keys() for item in required_items):
                if "info" in resp.keys():
                    self.logger().info(f"Unable to get price. {resp['info']}")
                else:
                    self.logger().info(f"Missing data from price result. Incomplete return result for ({resp.keys()})")
            else:
                gas_limit = resp["gasLimit"]
                gas_price = resp["gasPrice"]
                gas_cost = resp["gasCost"]
                price = resp["price"]
                account_standing = {
                    "allowances": self._allowances,
                    "balances": self._account_balances,
                    "base": base,
                    "quote": quote,
                    "amount": amount,
                    "side": side,
                    "gas_limit": gas_limit,
                    "gas_price": gas_price,
                    "gas_cost": gas_cost,
                    "price": price,
                    "swaps": len(resp["swaps"])
                }
                exceptions = check_transaction_exceptions(account_standing)
                for index in range(len(exceptions)):
                    self.logger().info(f"Warning! [{index+1}/{len(exceptions)}] {side} order - {exceptions[index]}")

                if price is not None and len(exceptions) == 0:
                    return Decimal(str(price))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting quote price for {trading_pair}  {side} order for {amount} amount.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        """
        This is simply the quote price
        """
        return await self.get_quote_price(trading_pair, is_buy, amount)

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal) -> str:
        """
        Buys an amount of base token for a given price (or cheaper).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The maximum price for the order.
        :return: A newly created order id (internal).
        """
        return self.place_order(True, trading_pair, amount, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal) -> str:
        """
        Sells an amount of base token for a given price (or at a higher price).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The minimum price for the order.
        :return: A newly created order id (internal).
        """
        return self.place_order(False, trading_pair, amount, price)

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal) -> str:
        """
        Places an order.
        :param is_buy: True for buy order
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param price: The minimum price for the order.
        :return: A newly created order id (internal).
        """
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
        Calls buy or sell API end point to place an order, starts tracking the order and triggers relevant order events.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param price: The order price
        """

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        base, quote = trading_pair.split("-")
        await self._update_nonce()
        api_params = {"base": base,
                      "quote": quote,
                      "side": trade_type.name.upper(),
                      "amount": str(amount),
                      "limitPrice": str(price),
                      "nonce": self._nonce,
                      }
        try:
            order_result = await self._api_request("post", f"{self.base_path}/trade", api_params)
            hash = order_result.get("txHash")
            gas_price = order_result.get("gasPrice")
            gas_limit = order_result.get("gasLimit")
            gas_cost = order_result.get("gasCost")
            self.start_tracking_order(order_id, None, trading_pair, trade_type, price, amount, gas_price)
            tracked_order = self._in_flight_orders.get(order_id)

            if tracked_order is not None:
                self.logger().info(f"Created {trade_type.name} order {order_id} txHash: {hash} "
                                   f"for {amount} {trading_pair} on {self._chain_info.get('name', '--')}. Estimated Gas Cost: {gas_cost} "
                                   f" (gas limit: {gas_limit}, gas price: {gas_price})")
                tracked_order.update_exchange_order_id(hash)
                tracked_order.gas_price = gas_price
            if hash is not None:
                tracked_order.fee_asset = self._chain_info["nativeCurrency"]["symbol"]
                tracked_order.executed_amount_base = amount
                tracked_order.executed_amount_quote = amount * price
                event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
                event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
                self.trigger_event(event_tag, event_class(self.current_timestamp, OrderType.LIMIT, trading_pair, amount,
                                                          price, order_id, hash))
            else:
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} swap order to {self.name} on {self._chain_info['name']} for "
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
                             trading_pair: str = "",
                             trade_type: TradeType = TradeType.BUY,
                             price: Decimal = s_decimal_0,
                             amount: Decimal = s_decimal_0,
                             gas_price: Decimal = s_decimal_0):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = GatewayInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=trade_type,
            price=price,
            amount=amount,
            gas_price=gas_price
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def _update_approval_order_status(self, tracked_orders: GatewayInFlightOrder):
        """
        Calls REST API to get status update for each in-flight order.
        This function can also be used to update status of simple swap orders.
        """
        if len(tracked_orders) > 0:
            tasks = []
            for tracked_order in tracked_orders:
                order_id = await tracked_order.get_exchange_order_id()
                tasks.append(self._api_request("post",
                                               "eth/poll",
                                               {"txHash": order_id}))
            update_results = await safe_gather(*tasks, return_exceptions=True)
            for tracked_order, update_result in zip(tracked_orders, update_results):
                self.logger().info(f"Polling for order status updates of {len(tasks)} orders.")
                if isinstance(update_result, Exception):
                    raise update_result
                if "txHash" not in update_result:
                    self.logger().info(f"_update_order_status txHash not in resp: {update_result}")
                    continue
                if update_result["confirmed"] is True:
                    if update_result["receipt"]["status"] == 1:
                        if tracked_order in self.approval_orders:
                            self.logger().info(f"Approval transaction id {update_result['txHash']} confirmed.")
                        else:
                            gas_used = update_result["receipt"]["gasUsed"]
                            gas_price = tracked_order.gas_price
                            fee = Decimal(str(gas_used)) * Decimal(str(gas_price)) / Decimal(str(1e9))
                            self.trigger_event(
                                MarketEvent.OrderFilled,
                                OrderFilledEvent(
                                    self.current_timestamp,
                                    tracked_order.client_order_id,
                                    tracked_order.trading_pair,
                                    tracked_order.trade_type,
                                    tracked_order.order_type,
                                    Decimal(str(tracked_order.price)),
                                    Decimal(str(tracked_order.amount)),
                                    TradeFee(0.0, [(tracked_order.fee_asset, Decimal(str(fee)))]),
                                    exchange_trade_id=order_id
                                )
                            )
                            tracked_order.last_state = "FILLED"
                            self.logger().info(f"The {tracked_order.trade_type.name} order "
                                               f"{tracked_order.client_order_id} has completed "
                                               f"according to order status API.")
                            event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY \
                                else MarketEvent.SellOrderCompleted
                            event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY \
                                else SellOrderCompletedEvent
                            self.trigger_event(event_tag,
                                               event_class(self.current_timestamp,
                                                           tracked_order.client_order_id,
                                                           tracked_order.base_asset,
                                                           tracked_order.quote_asset,
                                                           tracked_order.fee_asset,
                                                           tracked_order.executed_amount_base,
                                                           tracked_order.executed_amount_quote,
                                                           float(fee),
                                                           tracked_order.order_type))
                        self.stop_tracking_order(tracked_order.client_order_id)
                    else:
                        self.logger().info(
                            f"The market order {tracked_order.client_order_id} has failed according to order status API. ")
                        self.trigger_event(MarketEvent.OrderFailure,
                                           MarketOrderFailureEvent(
                                               self.current_timestamp,
                                               tracked_order.client_order_id,
                                               tracked_order.order_type
                                           ))
                        self.stop_tracking_order(tracked_order.client_order_id)

    async def _update_order_status(self, tracked_orders: GatewayInFlightOrder):
        """
        Calls REST API to get status update for each in-flight amm orders.
        """
        await self._update_approval_order_status(tracked_orders)

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("1e-15")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal("1e-15")

    @property
    def ready(self):
        return all(self.status_dict.values())

    def has_allowances(self) -> bool:
        """
        Checks if all tokens have allowance (an amount approved)
        """
        return len(self._allowances.values()) == len(self._tokens) and \
            all(amount > s_decimal_0 for amount in self._allowances.values())

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "allowances": self.has_allowances() if self._trading_required else True
        }

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._auto_approve_task = safe_ensure_future(self.auto_approve())

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._auto_approve_task is not None:
            self._auto_approve_task.cancel()
            self._auto_approve_task = None
        if self._get_chain_info_task is not None:
            self._get_chain_info_task.cancel()
            self._get_chain_info_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            response = await self._api_request("get", "")
            if 'status' in response and response['status'] == 'ok':
                pass
            else:
                raise Exception(f"Error connecting to Gateway API. Response is {response}.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        if time.time() - self._last_poll_timestamp > self.POLL_INTERVAL:
            if self._poll_notifier is not None and not self._poll_notifier.is_set():
                self._poll_notifier.set()

    async def _update_nonce(self):
        """
        Call the gateway API to get the current nonce for self._wallet_private_key
        """
        resp_json = await self._api_request("post", "eth/nonce", {})
        self._nonce = resp_json['nonce']

    async def _status_polling_loop(self):
        await self._update_balances(on_interval = False)
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(on_interval = True),
                    self._update_approval_order_status(self.approval_orders),
                    self._update_order_status(self.amm_orders)
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch balances from Gateway API.")

    async def _update_balances(self, on_interval = False):
        """
        Calls Eth API to update total and available balances.
        """
        last_tick = self._last_balance_poll_timestamp
        current_tick = self.current_timestamp
        if not on_interval or (current_tick - last_tick) > self.UPDATE_BALANCE_INTERVAL:
            self._last_balance_poll_timestamp = current_tick
            local_asset_names = set(self._account_balances.keys())
            remote_asset_names = set()
            resp_json = await self._api_request("post",
                                                "eth/balances",
                                                {"tokenSymbols": list(self._tokens)})
            for token, bal in resp_json["balances"].items():
                self._account_available_balances[token] = Decimal(str(bal))
                self._account_balances[token] = Decimal(str(bal))
                remote_asset_names.add(token)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

            self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
            self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            ssl_ctx = ssl.create_default_context(cafile=GATEAWAY_CA_CERT_PATH)
            ssl_ctx.load_cert_chain(GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH)
            conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            self._shared_client = aiohttp.ClientSession(connector=conn)
        return self._shared_client

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: A dictionary of required params for the end point
        :returns A response in json format.
        """
        base_url = f"https://{global_config_map['gateway_api_host'].value}:" \
                   f"{global_config_map['gateway_api_port'].value}"
        url = f"{base_url}/{path_url}"
        client = await self._http_client()
        if method == "get":
            if len(params) > 0:
                response = await client.get(url, params=params)
            else:
                response = await client.get(url)
        elif method == "post":
            params["privateKey"] = self._wallet_private_key
            if params["privateKey"][:2] != "0x":
                params["privateKey"] = "0x" + params["privateKey"]
            response = await client.post(url, json=params)
        parsed_response = json.loads(await response.text())
        if response.status != 200:
            err_msg = ""
            if "error" in parsed_response:
                err_msg = f" Message: {parsed_response['error']}"
            elif "message" in parsed_response:
                err_msg = f" Message: {parsed_response['message']}"
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.{err_msg}")
        if "error" in parsed_response:
            raise Exception(f"Error: {parsed_response['error']} {parsed_response['message']}")

        return parsed_response

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        return []

    @property
    def in_flight_orders(self) -> Dict[str, GatewayInFlightOrder]:
        return self._in_flight_orders
