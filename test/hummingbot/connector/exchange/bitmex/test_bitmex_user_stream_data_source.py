import asyncio
import unittest
from typing import Any, Awaitable, Dict, Optional
from unittest.mock import AsyncMock, patch

import ujson
from aioresponses.core import aioresponses

import hummingbot.connector.exchange.bitmex.constants as CONSTANTS
from hummingbot.connector.exchange.bitmex.bitmex_auth import BitmexAuth
from hummingbot.connector.exchange.bitmex.bitmex_user_stream_data_source import BitmexUserStreamDataSource
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BitmexUserStreamDataSourceUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.domain = CONSTANTS.TESTNET_DOMAIN

        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.emulated_time = 1640001112.223
        self.auth = BitmexAuth(api_key=self.api_key,
                               api_secret=self.secret_key)
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.data_source = BitmexUserStreamDataSource(
            auth=self.auth, domain=self.domain, throttler=self.throttler
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mock_done_event = asyncio.Event()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _mock_responses_done_callback(self, *_, **__):
        self.mock_done_event.set()

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _error_response(self) -> Dict[str, Any]:
        resp = {"code": "ERROR CODE", "msg": "ERROR MESSAGE"}

        return resp

    def _simulate_user_update_event(self):
        # Order Trade Update
        resp = {
            "table": "execution",
            "data": [{
                "orderID": "1",
                "clordID": "2",
                "price": 20,
                "orderQty": 100,
                "symbol": "COINALPHA_HBOT",
                "side": "Sell",
                "leavesQty": "1"
            }],
        }
        return ujson.dumps(resp)

    def time(self):
        # Implemented to emulate a TimeSynchronizer
        return self.emulated_time

    def test_last_recv_time(self):
        # Initial last_recv_time
        self.assertEqual(0, self.data_source.last_recv_time)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_create_websocket_connection_log_exception(self, mock_ws):
        mock_ws.side_effect = Exception("TEST ERROR.")

        msg_queue = asyncio.Queue()
        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))
        except asyncio.exceptions.TimeoutError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds... Error: TEST ERROR.",
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_create_websocket_connection_failed(self, mock_api, mock_ws):
        mock_ws.side_effect = Exception("TEST ERROR.")

        msg_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))

        try:
            self.async_run_with_timeout(msg_queue.get())
        except asyncio.exceptions.TimeoutError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds... Error: TEST ERROR.",
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_iter_message_throws_exception(self, _, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        mock_ws.return_value.closed = False
        mock_ws.return_value.close.side_effect = Exception

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))

        try:
            self.async_run_with_timeout(msg_queue.get())
        except Exception:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds... Error: TEST ERROR",
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_successful(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._simulate_user_update_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))

        msg = self.async_run_with_timeout(msg_queue.get())
        self.assertTrue(msg, self._simulate_user_update_event)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_api, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())
