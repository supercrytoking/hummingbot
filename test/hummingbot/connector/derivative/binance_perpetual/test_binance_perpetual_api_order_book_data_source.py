import asyncio
import re
import ujson
import unittest

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS

from aioresponses.core import aioresponses
from typing import (
    Any,
    Dict,
)
from unittest.mock import AsyncMock, patch

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.connector.derivative.binance_perpetual import binance_perpetual_utils as utils
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source import BinancePerpetualAPIOrderBookDataSource
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BinancePerpetualAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = "binance_perpetual_testnet"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None

        self.data_source = BinancePerpetualAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                                  domain=self.domain,
                                                                  )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _orderbook_update_event(self):
        resp = {
            "stream": f"{self.ex_trading_pair.lower()}@depth",
            "data": {
                "e": "depthUpdate",
                "E": 1631591424198,
                "T": 1631591424189,
                "s": self.ex_trading_pair,
                "U": 752409354963,
                "u": 752409360466,
                "pu": 752409354901,
                "b": [
                    [
                        "43614.31",
                        "0.000"
                    ],

                ],
                "a": [
                    [
                        "45277.14",
                        "0.257"
                    ],

                ]
            }
        }
        return ujson.dumps(resp)

    def _orderbook_trade_event(self):
        resp = {
            "stream": f"{self.ex_trading_pair.lower()}@aggTrade",
            "data": {
                "e": "aggTrade",
                "E": 1631594403486,
                "a": 817295132,
                "s": self.ex_trading_pair,
                "p": "45266.16",
                "q": "2.206",
                "f": 1437689393,
                "l": 1437689407,
                "T": 1631594403330,
                "m": False
            }
        }
        return ujson.dumps(resp)

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = utils.rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Dict[str, Any] = {
            # Truncated responses
            "lastPrice": "10.0",
        }
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result: Dict[str, Any] = self.ev_loop.run_until_complete(
            self.data_source.get_last_traded_prices(trading_pairs=[self.trading_pair], domain=self.domain)
        )
        self.assertTrue(self.trading_pair in result)
        self.assertEqual(10.0, result[self.trading_pair])

    def test_get_throttler_instance(self):
        self.assertTrue(isinstance(self.data_source._get_throttler_instance(), AsyncThrottler))

    @aioresponses()
    def test_fetch_trading_pairs_failure(self, mock_api):
        url = utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400, body=ujson.dumps({"ERROR"}))

        result: Dict[str, Any] = self.ev_loop.run_until_complete(
            self.data_source.fetch_trading_pairs(domain=self.domain)
        )
        self.assertEqual(0, len(result))

    @aioresponses()
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils.convert_from_exchange_trading_pair")
    def test_fetch_trading_pairs_successful(self, mock_api, mock_utils):
        mock_utils.return_value = self.trading_pair
        url = utils.rest_url(path_url=CONSTANTS.EXCHANGE_INFO_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Dict[str, Any] = {
            # Truncated Responses
            "symbols": [
                {
                    "symbol": self.ex_trading_pair,
                    "pair": self.ex_trading_pair,
                    "baseAsset": self.base_asset,
                    "quoteAsset": self.quote_asset,
                    "status": "TRADING",
                },
                {
                    "symbol": "INACTIVEMARKET",
                    "status": "INACTIVE"
                }
            ],
        }
        mock_api.get(regex_url, status=200, body=ujson.dumps(mock_response))
        result: Dict[str, Any] = self.ev_loop.run_until_complete(
            self.data_source.fetch_trading_pairs(domain=self.domain)
        )
        self.assertEqual(1, len(result))

    @aioresponses()
    def test_get_snapshot_exception_raised(self, mock_api):
        url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=400, body=ujson.dumps({"ERROR"}))

        with self.assertRaises(IOError) as context:
            self.ev_loop.run_until_complete(
                self.data_source.get_snapshot(trading_pair=self.trading_pair, domain=self.domain)
            )

        self.assertEqual(str(context.exception), f"Error fetching Binance market snapshot for {self.trading_pair}.")

    @aioresponses()
    def test_get_snapshot_successful(self, mock_api):
        url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {
            "lastUpdateId": 1027024,
            "E": 1589436922972,
            "T": 1589436922959,
            "bids": [
                [
                    "10",
                    "1"
                ]
            ],
            "asks": [
                [
                    "11",
                    "1"
                ]
            ]
        }
        mock_api.get(regex_url, status=200, body=ujson.dumps(mock_response))

        result: Dict[str, Any] = self.ev_loop.run_until_complete(
            self.data_source.get_snapshot(trading_pair=self.trading_pair, domain=self.domain)
        )
        self.assertEqual(mock_response, result)

    @aioresponses()
    def test_get_new_order_book(self, mock_api):
        url = utils.rest_url(CONSTANTS.SNAPSHOT_REST_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {
            "lastUpdateId": 1027024,
            "E": 1589436922972,
            "T": 1589436922959,
            "bids": [
                [
                    "10",
                    "1"
                ]
            ],
            "asks": [
                [
                    "11",
                    "1"
                ]
            ]
        }
        mock_api.get(regex_url, status=200, body=ujson.dumps(mock_response))
        result = self.ev_loop.run_until_complete(
            self.data_source.get_new_order_book(trading_pair=self.trading_pair)
        )
        self.assertIsInstance(result, OrderBook)
        self.assertEqual(1027024, result.snapshot_uid)

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_cancelled_error_raised(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.recv.side_effect = lambda: (
            self._raise_exception(asyncio.CancelledError)
        )
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)
        self.assertEqual(msg_queue.qsize(), 0)

    @patch("asyncio.sleep")
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils.convert_from_exchange_trading_pair")
    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_logs_exception(self, mock_ws, mock_utils, *_):
        mock_utils.return_value = self.trading_pair
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }
        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, ujson.dumps(incomplete_resp))
        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, self._orderbook_update_event())

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        self.ev_loop.run_until_complete(msg_queue.get())

        self.assertTrue(self._is_logged("ERROR", "Unexpected error with Websocket connection. Retrying after 30 seconds..."))

    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils.convert_from_exchange_trading_pair")
    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_successful(self, mock_ws, mock_utils):
        mock_utils.return_value = self.trading_pair
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, self._orderbook_update_event())

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        result: OrderBookMessage = self.ev_loop.run_until_complete(msg_queue.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.DIFF, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(result.update_id, 752409360466)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])
        self.assertEqual(1, len(result.content["bids"]))
        self.assertEqual(1, len(result.content["asks"]))

    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_trades_cancelled_error_raised(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.recv.side_effect = lambda: (
            self._raise_exception(asyncio.CancelledError)
        )
        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)
        self.assertEqual(msg_queue.qsize(), 0)

    @patch("asyncio.sleep")
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils.convert_from_exchange_trading_pair")
    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_trades_logs_exception(self, mock_ws, mock_utils, *_):
        mock_utils.return_value = self.trading_pair
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }
        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, ujson.dumps(incomplete_resp))
        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, self._orderbook_trade_event())

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        self.ev_loop.run_until_complete(msg_queue.get())

        self.assertTrue(self._is_logged("ERROR", "Unexpected error with Websocket connection. Retrying after 30 seconds..."))

    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils.convert_from_exchange_trading_pair")
    @patch("websockets.connect", new_callable=AsyncMock)
    def test_listen_for_trades_successful(self, mock_ws, mock_utils):
        mock_utils.return_value = self.trading_pair
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.close.return_value = None

        self.mocking_assistant.add_websocket_text_message(mock_ws.return_value, self._orderbook_trade_event())

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        result: OrderBookMessage = self.ev_loop.run_until_complete(msg_queue.get())
        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.TRADE, result.type)
        self.assertTrue(result.has_trade_id)
        self.assertEqual(result.trade_id, 817295132)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])

    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source.BinancePerpetualAPIOrderBookDataSource.get_snapshot", new_callable=AsyncMock)
    def test_listen_for_order_book_snapshots_cancelled_error_raised(self, mock_get_snapshot):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_get_snapshot.side_effect = lambda *_, **__: (
            self._raise_exception(asyncio.CancelledError)
        )

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
            )
            self.ev_loop.run_until_complete(self.listening_task)

        self.assertEqual(0, msg_queue.qsize())

    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source.BinancePerpetualAPIOrderBookDataSource.get_snapshot", new_callable=AsyncMock)
    def test_listen_for_order_book_snapshots_logs_exception_error_with_response(self, mock_get_snapshot):
        msg_queue: asyncio.Queue = asyncio.Queue()

        mock_get_snapshot.return_value = {
            "m": 1,
            "i": 2,
        }

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertTrue(self._is_logged("ERROR", "Unexpected error occurred fetching orderbook snapshots. Retrying in 5 seconds..."))

    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source.BinancePerpetualAPIOrderBookDataSource.get_snapshot", new_callable=AsyncMock)
    def test_listen_for_order_book_snapshots_successful(self, mock_get_snapshot):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_get_snapshot.return_value = {
            "lastUpdateId": 1027024,
            "E": 1589436922972,
            "T": 1589436922959,
            "bids": [
                [
                    "10",
                    "1"
                ]
            ],
            "asks": [
                [
                    "11",
                    "1"
                ]
            ]
        }

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        result = self.ev_loop.run_until_complete(msg_queue.get())

        self.assertIsInstance(result, OrderBookMessage)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, result.type)
        self.assertTrue(result.has_update_id)
        self.assertEqual(result.update_id, 1027024)
        self.assertEqual(self.trading_pair, result.content["trading_pair"])
