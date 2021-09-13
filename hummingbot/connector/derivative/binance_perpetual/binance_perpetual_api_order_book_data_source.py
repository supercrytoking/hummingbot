import aiohttp
import asyncio
import logging
import pandas as pd
import time
import ujson
import websockets

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS

from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
from websockets.exceptions import ConnectionClosed

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.connector.derivative.binance_perpetual import binance_perpetual_utils as utils
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_order_book import BinancePerpetualOrderBook
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils import convert_to_exchange_trading_pair
from hummingbot.logger import HummingbotLogger


class BinancePerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(self, trading_pairs: List[str] = None, domain: str = "binance_perpetual", throttler: Optional[AsyncThrottler] = None):
        super().__init__(trading_pairs)
        self._order_book_create_function = lambda: OrderBook()
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()

    _bpobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bpobds_logger is None:
            cls._bpobds_logger = logging.getLogger(__name__)
        return cls._bpobds_logger

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str], domain: str = "binance_perpetual") -> Dict[str, float]:
        tasks = [cls.get_last_traded_price(t_pair, domain) for t_pair in trading_pairs]
        results = await safe_gather(*tasks)
        return {t_pair: result for t_pair, result in zip(trading_pairs, results)}

    @classmethod
    async def get_last_traded_price(cls, trading_pair: str, domain: str = "binance_perpetual") -> float:
        url = utils.rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL, domain=domain)
        params = {
            "symbol": convert_to_exchange_trading_pair(trading_pair)
        }
        async with aiohttp.ClientSession() as client:
            async with client.get(url=url, params=params) as resp:
                resp_json = await resp.json()
                return float(resp_json["lastPrice"])

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    @staticmethod
    async def fetch_trading_pairs(domain: str = "binance_perpetual", throttler: Optional[AsyncThrottler] = None) -> List[str]:
        url = utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=domain)
        throttler = throttler or BinancePerpetualAPIOrderBookDataSource._get_throttler_instance()
        async with throttler.execute_task(limit_id=CONSTANTS.EXCHANGE_INFO_URL):
            async with aiohttp.ClientSession() as client:
                async with client.get(url=url, timeout=10) as response:
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
                           domain: str = "binance_perpetual",
                           throttler: Optional[AsyncThrottler] = None) -> Dict[str, Any]:
        params = {
            "symbol": convert_to_exchange_trading_pair(trading_pair)
        }
        if limit != 0:
            params.update({"limit": str(limit)})
        url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain)
        throttler = throttler or BinancePerpetualAPIOrderBookDataSource._get_throttler_instance()
        async with throttler.execute_task(limit_id=CONSTANTS.SNAPSHOT_REST_URL):
            async with aiohttp.ClientSession() as client:
                async with client.get(url=url, params=params) as response:
                    response: aiohttp.ClientResponse = response
                    if response.status != 200:
                        raise IOError(f"Error fetching Binance market snapshot for {trading_pair}. "
                                      f"HTTP status is {response.status}.")
                    data: Dict[str, Any] = await response.json()
                    return data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_snapshot(trading_pair, 1000, self._domain, self._throttler)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
        return order_book

    async def ws_messages(self, client: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                try:
                    raw_msg: str = await asyncio.wait_for(client.recv(), timeout=30.0)
                    yield raw_msg
                except asyncio.TimeoutError:
                    await client.pong(data=b'')
        except ConnectionClosed:
            return
        finally:
            await client.close()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws_subscription_path: str = "/".join([f"{convert_to_exchange_trading_pair(trading_pair).lower()}@depth"
                                                      for trading_pair in self._trading_pairs])
                stream_url: str = f"{utils.wss_url(endpoint=CONSTANTS.PUBLIC_WS_ENDPOINT)}?streams={ws_subscription_path}"
                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self.ws_messages(ws):
                        msg_json = ujson.loads(raw_msg)
                        timestamp: float = time.time()
                        order_book_message: OrderBookMessage = BinancePerpetualOrderBook.diff_message_from_exchange(
                            msg_json,
                            timestamp
                        )
                        output.put_nowait(order_book_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with Websocket connection. Retrying after 30 seconds... ",
                                    exc_info=True)
                await asyncio.sleep(30.0)

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                ws_subscription_path: str = "/".join([f"{convert_to_exchange_trading_pair(trading_pair).lower()}@aggTrade"
                                                      for trading_pair in self._trading_pairs])
                stream_url = f"{utils.wss_url(endpoint=CONSTANTS.PUBLIC_WS_ENDPOINT)}?streams={ws_subscription_path}"
                async with websockets.connect(stream_url) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    async for raw_msg in self.ws_messages(ws):
                        msg_json = ujson.loads(raw_msg)
                        trade_msg: OrderBookMessage = BinancePerpetualOrderBook.trade_message_from_exchange(msg_json)
                        output.put_nowait(trade_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(30)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                async with aiohttp.ClientSession() as client:
                    for trading_pair in self._trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair, domain=self._domain)
                            snapshot_timestamp: float = time.time()
                            snapshot_msg: OrderBookMessage = BinancePerpetualOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                snapshot_timestamp,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_msg)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            await asyncio.sleep(5)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
