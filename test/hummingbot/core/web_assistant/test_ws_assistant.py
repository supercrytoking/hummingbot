import asyncio
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, PropertyMock, patch

import aiohttp

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSJSONRequest, WSRequest, WSResponse
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.core.web_assistant.ws_post_processors import WSPostProcessorBase
from hummingbot.core.web_assistant.ws_pre_processors import WSPreProcessorBase


class WSAssistantTest(unittest.TestCase):
    ev_loop: asyncio.AbstractEventLoop

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        for task in asyncio.all_tasks(cls.ev_loop):
            task.cancel()

    def setUp(self) -> None:
        super().setUp()
        aiohttp_client_session = aiohttp.ClientSession()
        self.ws_connection = WSConnection(aiohttp_client_session)
        self.ws_assistant = WSAssistant(self.ws_connection)
        self.mocking_assistant = NetworkMockingAssistant()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.connect")
    def test_connect(self, connect_mock):
        ws_url = "ws://some.url"
        ping_timeout = 10
        message_timeout = 20

        self.async_run_with_timeout(
            self.ws_assistant.connect(ws_url, ping_timeout=ping_timeout, message_timeout=message_timeout)
        )

        connect_mock.assert_called_with(ws_url=ws_url,
                                        ws_headers={},
                                        ping_timeout=ping_timeout,
                                        message_timeout=message_timeout)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.disconnect")
    def test_disconnect(self, disconnect_mock):
        self.async_run_with_timeout(self.ws_assistant.disconnect())

        disconnect_mock.assert_called()

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.send")
    def test_send(self, send_mock):
        sent_requests = []
        send_mock.side_effect = lambda r: sent_requests.append(r)
        payload = {"one": 1}
        request = WSJSONRequest(payload)

        self.async_run_with_timeout(self.ws_assistant.send(request))

        self.assertEqual(1, len(sent_requests))

        sent_request = sent_requests[0]

        self.assertNotEqual(id(request), id(sent_request))  # has been cloned
        self.assertEqual(request, sent_request)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.send")
    def test_send_pre_processes(self, send_mock):
        class SomePreProcessor(WSPreProcessorBase):
            async def pre_process(self, request_: RESTRequest) -> RESTRequest:
                request_.payload["two"] = 2
                return request_

        ws_assistant = WSAssistant(
            connection=self.ws_connection, ws_pre_processors=[SomePreProcessor()]
        )
        sent_requests = []
        send_mock.side_effect = lambda r: sent_requests.append(r)
        payload = {"one": 1}
        request = WSJSONRequest(payload)

        self.async_run_with_timeout(ws_assistant.send(request))

        sent_request = sent_requests[0]
        expected = {"one": 1, "two": 2}

        self.assertEqual(expected, sent_request.payload)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.send")
    def test_subscribe(self, send_mock):
        sent_requests = []
        send_mock.side_effect = lambda r: sent_requests.append(r)
        payload = {"one": 1}
        request = WSJSONRequest(payload)

        self.async_run_with_timeout(self.ws_assistant.subscribe(request))

        self.assertEqual(1, len(sent_requests))

        sent_request = sent_requests[0]

        self.assertNotEqual(id(request), id(sent_request))  # has been cloned
        self.assertEqual(request, sent_request)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.send")
    def test_ws_assistant_authenticates(self, send_mock):
        class Auth(AuthBase):
            async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
                pass

            async def ws_authenticate(self, request: WSRequest) -> WSRequest:
                request.payload["authenticated"] = True
                return request

        ws_assistant = WSAssistant(connection=self.ws_connection, auth=Auth())
        sent_requests = []
        send_mock.side_effect = lambda r: sent_requests.append(r)
        payload = {"one": 1}
        req = WSJSONRequest(payload)
        auth_req = WSJSONRequest(payload, is_auth_required=True)

        self.async_run_with_timeout(ws_assistant.send(req))
        self.async_run_with_timeout(ws_assistant.send(auth_req))

        sent_request = sent_requests[0]
        auth_sent_request = sent_requests[1]
        expected = {"one": 1}
        auth_expected = {"one": 1, "authenticated": True}

        self.assertEqual(expected, sent_request.payload)
        self.assertEqual(auth_expected, auth_sent_request.payload)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.receive")
    def test_receive(self, receive_mock):
        data = {"one": 1}
        response_mock = WSResponse(data)
        receive_mock.return_value = response_mock

        response = self.async_run_with_timeout(self.ws_assistant.receive())

        self.assertEqual(data, response.data)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_receive_plain_text(self, ws_connect_mock):
        data = "pong"
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=data)
        self.async_run_with_timeout(self.ws_assistant.connect(ws_url="test.url"))
        response = self.async_run_with_timeout(self.ws_assistant.receive())

        self.assertEqual(data, response.data)

    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.receive")
    def test_receive_post_processes(self, receive_mock):
        class SomePostProcessor(WSPostProcessorBase):
            async def post_process(self, response_: WSResponse) -> WSResponse:
                response_.data["two"] = 2
                return response_

        ws_assistant = WSAssistant(
            connection=self.ws_connection, ws_post_processors=[SomePostProcessor()]
        )
        data = {"one": 1}
        response_mock = WSResponse(data)
        receive_mock.return_value = response_mock

        response = self.async_run_with_timeout(ws_assistant.receive())

        expected = {"one": 1, "two": 2}

        self.assertEqual(expected, response.data)

    @patch(
        "hummingbot.core.web_assistant.connections.ws_connection.WSConnection.connected",
        new_callable=PropertyMock,
    )
    @patch("hummingbot.core.web_assistant.connections.ws_connection.WSConnection.receive")
    def test_iter_messages(self, receive_mock, connected_mock):
        connected_mock.return_value = True
        data = {"one": 1}
        response_mock = WSResponse(data)
        receive_mock.return_value = response_mock
        iter_messages_iterator = self.ws_assistant.iter_messages()

        response = self.async_run_with_timeout(iter_messages_iterator.__anext__())

        self.assertEqual(data, response.data)

        connected_mock.return_value = False

        with self.assertRaises(StopAsyncIteration):
            self.async_run_with_timeout(iter_messages_iterator.__anext__())
