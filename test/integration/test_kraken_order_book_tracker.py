#!/usr/bin/env python
import math
import time
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.market.kraken.kraken_order_book_tracker import KrakenOrderBookTracker
from hummingbot.market.kraken.kraken_api_order_book_data_source import KrakenAPIOrderBookDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
import asyncio
import aiohttp
import logging
from typing import (
    Dict,
    Optional,
    List,
)
import unittest


class KrakenOrderBookTrackerUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: KrakenOrderBookTracker = KrakenOrderBookTracker()
        cls.order_book_tracker_task: asyncio.Task = safe_ensure_future(cls.order_book_tracker.start())
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())
    
    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1)
        
    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    def test_data_source(self):
        data_source: KrakenAPIOrderBookDataSource = self.order_book_tracker.data_source
        self.assertIsInstance(self.order_book_tracker.data_source, KrakenAPIOrderBookDataSource)

    def test_name(self):
        self.assertEqual(self.order_book_tracker.exchange_name, "kraken")

    def test_start_stop(self):
        self.run_async(self.order_book_tracker.start())
        self.assertTrue(asyncio.isfuture(self.order_book_tracker._order_book_snapshot_router_task))
        self.order_book_tracker.stop()
        self.assertIsNone(self.order_book_tracker._order_book_snapshot_router_task)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
