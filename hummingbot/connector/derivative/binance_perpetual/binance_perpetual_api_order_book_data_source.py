import asyncio
import logging
import pandas as pd
import time


from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils as utils
import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS

from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_order_book import BinancePerpetualOrderBook
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class BinancePerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):

    DIFF_STREAM_ID = 1
    TRADE_STREAM_ID = 2
    HEARTBEAT_TIME_INTERVAL = 30.0

    _bpobds_logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str] = None,
        domain: str = CONSTANTS.DOMAIN,
        throttler: Optional[AsyncThrottler] = None,
        api_factory: Optional[WebAssistantsFactory] = None
    ):
        super().__init__(trading_pairs)
        self._api_factory: WebAssistantsFactory = api_factory or utils.build_api_factory()
        self._ws_assistant: Optional[WSAssistant] = None
        self._order_book_create_function = lambda: OrderBook()
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpobds_logger is None:
            cls._bpobds_logger = logging.getLogger(__name__)
        return cls._bpobds_logger

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    @classmethod
    async def get_last_traded_prices(cls, 
                                     trading_pairs: List[str], 
                                     domain: str = CONSTANTS.DOMAIN) -> Dict[str, float]:
        tasks = [cls.get_last_traded_price(t_pair, domain) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def get_last_traded_price(cls, trading_pair: str, domain: str = CONSTANTS.DOMAIN) -> float:
        api_factory = utils.build_api_factory()
        rest_assistant = await api_factory.get_rest_assistant()

        throttler = cls._get_throttler_instance()

        url = utils.rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL, domain=domain)
        params = {"symbol": utils.convert_to_exchange_trading_pair(trading_pair)}

        async with throttler.execute_task(CONSTANTS.TICKER_PRICE_CHANGE_URL):
            request = RESTRequest(
                method=RESTMethod.GET,
                url=url,
                params=params,
            )
            resp = await rest_assistant.call(request=request)
            resp_json = await resp.json()
            return float(resp_json["lastPrice"])

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    @staticmethod
    async def fetch_trading_pairs(domain: str = CONSTANTS.DOMAIN, 
                                  throttler: Optional[AsyncThrottler] = None) -> List[str]:
        api_factory = utils.build_api_factory()
        rest_assistant = await api_factory.get_rest_assistant()

        url = utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=domain)
        throttler = throttler or BinancePerpetualAPIOrderBookDataSource._get_throttler_instance()
        async with throttler.execute_task(limit_id=CONSTANTS.EXCHANGE_INFO_URL):
            request = RESTRequest(
                method=RESTMethod.GET,
                url=url,
            )
            response = await rest_assistant.call(request=request, timeout=10)

            if response.status == 200:
                data = await response.json()
                # fetch d["pair"] for binance perpetual
                raw_trading_pairs = [d["pair"] for d in data["symbols"] if d["status"] == "TRADING"]
                trading_pair_targets = [
                    f"{d['baseAsset']}-{d['quoteAsset']}" for d in data["symbols"] if d["status"] == "TRADING"
                ]
                trading_pair_list: List[str] = []
                for raw_trading_pair, pair_target in zip(raw_trading_pairs, trading_pair_targets):
                    trading_pair = utils.convert_from_exchange_trading_pair(raw_trading_pair)
                    if trading_pair is not None and trading_pair == pair_target:
                        trading_pair_list.append(trading_pair)
                return trading_pair_list
        return []

    @staticmethod
    async def get_snapshot(trading_pair: str,
                           limit: int = 1000,
                           domain: str = CONSTANTS.DOMAIN,
                           throttler: Optional[AsyncThrottler] = None) -> Dict[str, Any]:
        try:
            api_factory = utils.build_api_factory()
            rest_assistant = await api_factory.get_rest_assistant()

            params = {
                "symbol": utils.convert_to_exchange_trading_pair(trading_pair)
            }
            if limit != 0:
                params.update({"limit": str(limit)})
            url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain)
            throttler = throttler or BinancePerpetualAPIOrderBookDataSource._get_throttler_instance()
            async with throttler.execute_task(limit_id=CONSTANTS.SNAPSHOT_REST_URL):
                request = RESTRequest(
                    method=RESTMethod.GET,
                    url=url,
                    params=params,
                )
                response = await rest_assistant.call(request=request)
                if response.status != 200:
                    raise IOError(f"Error fetching Binance market snapshot for {trading_pair}.")
                data: Dict[str, Any] = await response.json()
                return data
        except asyncio.CancelledError:
            raise
        except Exception:
            raise

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair, 1000, self._domain, self._throttler)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
            snapshot, snapshot_timestamp, metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        ws = None
        while True:
            try:
                url = f"{utils.wss_url(CONSTANTS.PUBLIC_WS_ENDPOINT, self._domain)}"
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)

                payload = {
                    "method": "SUBSCRIBE",
                    "params": [
                        f"{utils.convert_to_exchange_trading_pair(trading_pair).lower()}@depth"
                        for trading_pair in self._trading_pairs
                    ],
                    "id": self.DIFF_STREAM_ID
                }
                subscribe_request: WSRequest = WSRequest(payload)
                await ws.send(subscribe_request)

                async for msg in ws.iter_messages():
                    json_msg = msg.data
                    if "result" in json_msg:
                        continue
                    timestamp: float = time.time()
                    order_book_message: OrderBookMessage = BinancePerpetualOrderBook.diff_message_from_exchange(
                        json_msg, timestamp
                    )
                    output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Websocket connection. Retrying after 30 seconds...",
                    exc_info=True
                )
                await self._sleep(30.0)
            finally:
                ws and await ws.disconnect()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=f"{utils.wss_url(CONSTANTS.PUBLIC_WS_ENDPOINT, self._domain)}", 
                                 ping_timeout=self.HEARTBEAT_TIME_INTERVAL)

                payload = {
                    "method": "SUBSCRIBE",
                    "params": [
                        f"{utils.convert_to_exchange_trading_pair(trading_pair).lower()}@aggTrade"
                        for trading_pair in self._trading_pairs
                    ],
                    "id": self.TRADE_STREAM_ID
                }
                subscribe_request: WSRequest = WSRequest(payload)
                await ws.send(subscribe_request)

                async for msg in ws.iter_messages():
                    json_msg = msg.data
                    if "result" in json_msg:
                        continue
                    trade_msg: OrderBookMessage = BinancePerpetualOrderBook.trade_message_from_exchange(json_msg)
                    output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error with Websocket connection. Retrying after 30 seconds...", exc_info=True
                )
                await self._sleep(30.0)
            finally:
                ws and await ws.disconnect()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair, domain=self._domain)
                    snapshot_timestamp: float = time.time()
                    snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
                        snapshot, snapshot_timestamp, metadata={"trading_pair": trading_pair}
                    )
                    output.put_nowait(snapshot_msg)
                    self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await self._sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error occurred fetching orderbook snapshots. Retrying in 5 seconds...", exc_info=True
                )
                await self._sleep(5.0)
