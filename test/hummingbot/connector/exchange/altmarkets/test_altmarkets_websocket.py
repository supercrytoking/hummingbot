import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants
from hummingbot.connector.exchange.altmarkets.altmarkets_websocket import AltmarketsWebsocket
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class AltmarketsWebsocketTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("websockets.connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.altmarkets.altmarkets_websocket.AltmarketsWebsocket.generate_request_id")
    def test_send_subscription_message(self, request_id_mock, ws_connect_mock):
        request_id_mock.return_value = 1234567899
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        throttler = AsyncThrottler(Constants.RATE_LIMITS)
        websocket = AltmarketsWebsocket(throttler=throttler)
        message = [Constants.WS_SUB["TRADES"].format(trading_pair="btcusdt")]

        self.async_run_with_timeout(websocket.connect())
        self.async_run_with_timeout(websocket.subscribe(message))
        self.async_run_with_timeout(websocket.unsubscribe(message))

        sent_requests = self.mocking_assistant.text_messages_sent_through_websocket(ws_connect_mock.return_value)
        sent_subscribe_message = json.loads(sent_requests[0])
        expected_subscribe_message = {"event": "subscribe", "id": 1234567899, "streams": ['btcusdt.trades']}
        self.assertEquals(expected_subscribe_message, sent_subscribe_message)
        sent_unsubscribe_message = json.loads(sent_requests[1])
        expected_unsubscribe_message = {"event": "unsubscribe", "id": 1234567899, "streams": ['btcusdt.trades']}
        self.assertEquals(expected_unsubscribe_message, sent_unsubscribe_message)
