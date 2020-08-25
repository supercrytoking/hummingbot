#!/usr/bin/env python
import asyncio
import logging
import time
import aiohttp
import pandas as pd
import hummingbot.market.crypto_com.crypto_com_constants as constants

from typing import Optional, List, Dict, Any
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.market.crypto_com.crypto_com_order_book_tracker_entry import CryptoComOrderBookTrackerEntry
from hummingbot.market.crypto_com.crypto_com_active_order_tracker import CryptoComActiveOrderTracker
from hummingbot.market.crypto_com.crypto_com_order_book import CryptoComOrderBook
from hummingbot.market.crypto_com.crypto_com_websocket import CryptoComWebsocket
from hummingbot.market.crypto_com.crypto_com_utils import merge_dicts, ms_timestamp_to_s


class CryptoComAPIOrderBookDataSource(OrderBookTrackerDataSource):
    MAX_RETRIES = 20
    MESSAGE_TIMEOUT = 30.0
    SNAPSHOT_TIMEOUT = 10.0

    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pairs: List[str] = None):
        super().__init__(trading_pairs)
        self._trading_pairs: List[str] = trading_pairs
        self._snapshot_msg: Dict[str, any] = {}

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        result = {}
        async with aiohttp.ClientSession() as client:
            resp = await client.get(f"{constants.REST_URL}/public/get-ticker")
            resp_json = await resp.json()
            for t_pair in trading_pairs:
                last_trade = [o["a"] for o in resp_json["result"]["data"] if o["i"] == t_pair]
                if last_trade and last_trade[0] is not None:
                    result[t_pair] = last_trade[0]
        return result

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have symbol as index and include USDVolume, baseAsset and quoteAsset
        """
        async with aiohttp.ClientSession() as client:

            markets_response, tickers_response = await safe_gather(
                client.get(f"{constants.REST_URL}/public/get-instruments"),
                client.get(f"{constants.REST_URL}/public/get-ticker"),
            )

            markets_response: aiohttp.ClientResponse = markets_response
            tickers_response: aiohttp.ClientResponse = tickers_response

            if markets_response.status != 200:
                raise IOError(
                    f"Error fetching active {constants.EXCHANGE_NAME} markets information. " f"HTTP status is {markets_response.status}."
                )
            if tickers_response.status != 200:
                raise IOError(
                    f"Error fetching active {constants.EXCHANGE_NAME} tickers information. " f"HTTP status is {tickers_response.status}."
                )

            markets_data, tickers_data = await safe_gather(
                markets_response.json(), tickers_response.json()
            )

            markets_data: Dict[str, Any] = {item["instrument_name"]: item for item in markets_data["result"]["instruments"]}
            tickers_data: Dict[str, Any] = {
                item["i"]: {
                    "instrument_name": item["i"],
                    "bid_price": item["b"],
                    "ask_price": item["k"],
                    "last_price": item["a"],
                    "timestamp": item["t"],
                    "volume": item["v"],
                    "high": item["h"],
                    "low": item["l"],
                    "change": item["c"],
                }
                for item in tickers_data["result"]["data"]
            }

            data_union = merge_dicts(tickers_data, markets_data)

            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=list(data_union.values()), index="trading_pair")

            btc_usd_price: float = float(all_markets.loc["BTC_USDT"]["last_price"])
            cro_usd_price: float = float(all_markets.loc["CRO_USDT"]["last_price"])

            usd_volume: List[float] = [
                (
                    volume * last_price if trading_pair.endswith(("USD", "USDT")) else
                    volume * last_price * btc_usd_price if trading_pair.endswith("BTC") else
                    volume * last_price * cro_usd_price if trading_pair.endswith("CRO") else
                    volume
                )
                for trading_pair, volume, last_price in zip(
                    all_markets.index,
                    # uses 24 hour volume, @TODO: discuss with core team
                    all_markets["volume"].astype("float"),
                    all_markets["last_price"].astype("float")
                )
            ]

            all_markets.loc[:, "USDVolume"] = usd_volume
            await client.close()

            return all_markets.sort_values("USDVolume", ascending=False)

    @staticmethod
    async def get_order_book_data(trading_pair: str) -> Dict[str, any]:
        """
        Get whole orderbook
        """
        async with aiohttp.ClientSession() as client:
            orderbook_response = await client.get(
                f"{constants.REST_URL}/public/get-book?depth=150&instrument_name={trading_pair}"
            )

            if orderbook_response.status != 200:
                raise IOError(
                    f"Error fetching OrderBook for {trading_pair} at {constants.EXCHANGE_NAME}. "
                    f"HTTP status is {orderbook_response.status}."
                )

            orderbook_data: List[Dict[str, Any]] = await safe_gather(orderbook_response.json())
            orderbook_data = orderbook_data[0]["result"]["data"][0]

        return orderbook_data

    async def get_new_order_book(self, trading_pair: str) -> OrderBook:
        snapshot: Dict[str, Any] = await self.get_order_book_data(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = CryptoComOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        order_book = self.order_book_create_function()
        active_order_tracker: CryptoComActiveOrderTracker = CryptoComActiveOrderTracker()
        bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
        order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)
        return order_book

    async def get_tracking_pairs(self) -> Dict[str, CryptoComOrderBookTrackerEntry]:
        trading_pairs: List[str] = await self.get_trading_pairs()
        tracking_pairs: Dict[str, CryptoComOrderBookTrackerEntry] = {}

        number_of_pairs: int = len(trading_pairs)
        for index, trading_pair in enumerate(trading_pairs):
            try:
                snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair)
                snapshot_timestamp: int = ms_timestamp_to_s(snapshot["t"])
                snapshot_msg: OrderBookMessage = CryptoComOrderBook.snapshot_message_from_exchange(
                    snapshot,
                    snapshot_timestamp,
                    metadata={"trading_pair": trading_pair}
                )
                order_book: OrderBook = self.order_book_create_function()
                active_order_tracker: CryptoComActiveOrderTracker = CryptoComActiveOrderTracker()
                bids, asks = active_order_tracker.convert_snapshot_message_to_order_book_row(snapshot_msg)
                order_book.apply_snapshot(bids, asks, snapshot_msg.update_id)

                tracking_pairs[trading_pair] = CryptoComOrderBookTrackerEntry(
                    trading_pair,
                    snapshot_timestamp,
                    order_book,
                    active_order_tracker
                )
                self.logger().info(f"Initialized order book for {trading_pair}. "
                                   f"{index+1}/{number_of_pairs} completed.")
                await asyncio.sleep(0.6)
            except IOError:
                self.logger().network(
                    f"Error getting snapshot for {trading_pair}.",
                    exc_info=True,
                    app_warning_msg=f"Error getting snapshot for {trading_pair}. Check network connection."
                )
            except Exception:
                self.logger().error(f"Error initializing order book for {trading_pair}. ", exc_info=True)

        return tracking_pairs

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for trades using websocket trade channel
        """
        while True:
            try:
                ws = CryptoComWebsocket()
                await ws.connect()

                await ws.subscribe(list(map(
                    lambda pair: f"trade.{pair}",
                    self._trading_pairs
                )))

                async for response in ws.onMessage():
                    if response.get("result") is None:
                        continue

                    for trade in response["result"]["data"]:
                        trade: Dict[Any] = trade
                        trade_timestamp: int = ms_timestamp_to_s(trade["t"])
                        trade_msg: OrderBookMessage = CryptoComOrderBook.trade_message_from_exchange(
                            trade,
                            trade_timestamp,
                            metadata={"trading_pair": trade["i"]}
                        )
                        output.put_nowait(trade_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
            finally:
                await ws.disconnect()

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook diffs using websocket book channel
        """
        while True:
            try:
                ws = CryptoComWebsocket()
                await ws.connect()

                await ws.subscribe(list(map(
                    lambda pair: f"book.{pair}.150",
                    self._trading_pairs
                )))

                async for response in ws.onMessage():
                    if response.get("result") is None:
                        continue

                    diff = response["result"]["data"][0]
                    diff_timestamp: int = ms_timestamp_to_s(diff["t"])
                    orderbook_msg: OrderBookMessage = CryptoComOrderBook.diff_message_from_exchange(
                        diff,
                        diff_timestamp,
                        metadata={"trading_pair": response["result"]["instrument_name"]}
                    )
                    output.put_nowait(orderbook_msg)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error with WebSocket connection.",
                    exc_info=True,
                    app_warning_msg="Unexpected error with WebSocket connection. Retrying in 30 seconds. "
                                    "Check network connection."
                )
                await asyncio.sleep(30.0)
            finally:
                await ws.disconnect()

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """
        Listen for orderbook snapshots by fetching orderbook
        """
        while True:
            try:
                for trading_pair in self._trading_pairs:
                    try:
                        snapshot: Dict[str, any] = await self.get_order_book_data(trading_pair)
                        snapshot_timestamp: int = ms_timestamp_to_s(snapshot["t"])
                        snapshot_msg: OrderBookMessage = CryptoComOrderBook.snapshot_message_from_exchange(
                            snapshot,
                            snapshot_timestamp,
                            metadata={"trading_pair": trading_pair}
                        )
                        output.put_nowait(snapshot_msg)
                        self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                        # Be careful not to go above API rate limits.
                        await asyncio.sleep(5.0)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.logger().network(
                            "Unexpected error with WebSocket connection.",
                            exc_info=True,
                            app_warning_msg="Unexpected error with WebSocket connection. Retrying in 5 seconds. "
                                            "Check network connection."
                        )
                        await asyncio.sleep(5.0)
                this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                delta: float = next_hour.timestamp() - time.time()
                await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
