#!/usr/bin/env python
import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Optional, Dict, List, Set, Deque

from hummingbot.core.data_type.order_book_message import BittrexOrderBookMessage
from hummingbot.core.data_type.order_book_tracker_entry import BittrexOrderBookTrackerEntry
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_tracker import (
    OrderBookTracker,
    OrderBookTrackerDataSourceType
)
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.bittrex.bittrex_api_order_book_data_source import BittrexAPIOrderBookDataSource
from hummingbot.market.bittrex.bittrex_order_book import BittrexOrderBook


class BittrexOrderBookTracker(OrderBookTracker):
    _btobt_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._btobt_logger is None:
            cls._btobt_logger = logging.getLogger(__name__)
        return cls._btobt_logger

    def __init__(self,
                 data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None):
        super().__init__(data_source_type=data_source_type)

        self._ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[OrderBookTrackerDataSource] = None
        self._order_book_snapshot_stream: asyncio.Queue = asyncio.Queue()
        self._order_book_diff_stream: asyncio.Queue = asyncio.Queue()
        self._process_msg_deque_task: Optional[asyncio.Task] = None
        self._past_diffs_windows: Dict[str, Deque] = {}
        self._order_books: Dict[str, BittrexOrderBook] = {}
        self._saved_message_queues: Dict[str, Deque[BittrexOrderBookMessage]] = defaultdict(
            lambda: deque(maxlen=1000))
        self._symbols: Optional[List[str]] = symbols

    @property
    def data_source(self) -> OrderBookTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is OrderBookTrackerDataSourceType.EXCHANGE_API:
                self._data_source = BittrexAPIOrderBookDataSource(symbols=self._symbols)
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "bittrex"

    async def _refresh_tracking_tasks(self):
        """
        Starts tracking for any new trading pairs, and stop tracking for any inactive trading pairs.
        """
        tracking_symbols: Set[str] = set([key for key in self._tracking_tasks.keys()
                                          if not self._tracking_tasks[key].done()])
        available_pairs: Dict[str, BittrexOrderBookTrackerEntry] = await self.data_source.get_tracking_pairs()
        available_symbols: Set[str] = set(available_pairs.keys())
        new_symbols: Set[str] = available_symbols - tracking_symbols
        deleted_symbols: Set[str] = tracking_symbols - available_symbols

        for symbol in new_symbols:
            order_book_tracker_entry: BittrexOrderBookTrackerEntry = available_pairs[symbol]
            self._order_books[symbol] = order_book_tracker_entry.order_book
            self._tracking_message_queues[symbol] = asyncio.Queue()
            self._tracking_tasks[symbol] = asyncio.ensure_future(self._track_single_book(symbol))
            self.logger().info(f"Started order book tracking for {symbol}.")

        for symbol in deleted_symbols:
            self._tracking_tasks[symbol].cancel()
            del self._tracking_tasks[symbol]
            del self._order_books[symbol]
            del self._active_order_trackers[symbol]
            del self._tracking_message_queues[symbol]
            self.logger().info(f"Stopped order book tracking for {symbol}.")

    async def _order_book_diff_router(self):
        """
        Route the real-time order book diff messages to the correct order book.
        """
        last_message_timestamp: float = time.time()
        message_queued: int = 0
        message_accepted: int = 0
        message_rejected: int = 0
        while True:
            try:
                ob_message: BittrexOrderBookMessage = await self._order_book_diff_stream.get()
                symbol: str = ob_message.symbol
                if symbol not in self._tracking_message_queues:
                    message_queued += 1
                    # Save diff messages received before snaphsots are ready
                    self._saved_message_queues[symbol].append(ob_message)
                    continue
                message_queue: asyncio.Queue = self._tracking_message_queues[symbol]
                # Check the order book's initial update ID. If it's larger, don't bother.
                order_book: BittrexOrderBook = self._order_books[symbol]

                if order_book.snapshot_uid > ob_message.update_id:
                    message_rejected += 1
                    continue
                await message_queue.put(ob_message)
                message_accepted += 1

                # Log some statistics
                now: float = time.time()
                if int(now / 60.0) > int(last_message_timestamp / 60.0):
                    self.logger().debug(f"Diff message processed: "
                                        f"{message_accepted}, "
                                        f"rejected: {message_rejected}, "
                                        f"queued: {message_queue}")
                    message_accepted = 0
                    message_rejected = 0
                    message_queue = 0

                last_message_timestamp = now

            except asyncio.CancelledError:
                raise

            except Exception:
                self.logger().network(
                    f"Unexpected error routing order book messages.",
                    exc_info=True,
                    app_warning_msg=f"Unexpected error routing order book messages. Retrying after 5 seconds."
                )
                await asyncio.sleep(5.0)

    async def _track_single_book(self, symbol: str):
        past_diffs_window: Deque[BittrexOrderBookMessage] = deque()
        self._past_diffs_windows[symbol] = past_diffs_window

        message_queue: asyncio.Queue = self._tracking_message_queues[symbol]
        order_book: BittrexOrderBook = self._order_books[symbol]

    async def start(self):
        self._order_book_diff_listener_task = safe_ensure_future(
            self.data_source.listen_for_order_book_diffs(self._ev_loop, self._order_book_diff_stream)
        )
        self._order_book_snapshot_listener_task = safe_ensure_future(
            self.data_source.listen_for_order_book_snapshots(self._ev_loop, self._order_book_snapshot_stream)
        )
        self._refresh_tracking_task = safe_ensure_future(
            self._refresh_tracking_loop()
        )
        self._order_book_diff_router_task = safe_ensure_future(
            self._order_book_diff_router()
        )
        self._order_book_snapshot_router_task = safe_ensure_future(
            self._order_book_snapshot_router()
        )

        await safe_gather(self._order_book_snapshot_listener_task,
                          self._order_book_diff_listener_task,
                          self._refresh_tracking_task
                          )
