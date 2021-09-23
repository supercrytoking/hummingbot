import asyncio
import functools
from collections import defaultdict, deque
from unittest.mock import PropertyMock, AsyncMock


class NetworkMockingAssistant:

    def __init__(self):
        super().__init__()

        self._response_text_queues = defaultdict(asyncio.Queue)
        self._response_json_queues = defaultdict(asyncio.Queue)
        self._response_status_queues = defaultdict(deque)
        self._sent_http_requests = defaultdict(asyncio.Queue)

        self._incoming_websocket_json_queues = defaultdict(asyncio.Queue)
        self._incoming_websocket_text_queues = defaultdict(asyncio.Queue)
        self._sent_websocket_json_messages = defaultdict(list)
        self._sent_websocket_text_messages = defaultdict(list)

        self._final_message = 'FinalDummyMessage'
        self._all_ws_delivered = asyncio.Event()

        self._ev_loop = asyncio.get_event_loop()

    @staticmethod
    def async_partial(function, *args, **kwargs):
        async def partial_func(*args2, **kwargs2):
            result = function(*args, *args2, **kwargs, **kwargs2)
            if asyncio.iscoroutinefunction(function):
                result = await result
            return result

        return partial_func

    def _get_next_api_response_status(self, http_mock):
        return self._response_status_queues[http_mock].popleft()

    async def _get_next_api_response_json(self, http_mock):
        return await self._response_json_queues[http_mock].get()

    async def _get_next_api_response_text(self, http_mock):
        return await self._response_text_queues[http_mock].get()

    def _handle_http_request(self, http_mock, url, headers=None, params=None, data=None, *args, **kwargs):
        response = AsyncMock()
        type(response).status = PropertyMock(side_effect=functools.partial(
            self._get_next_api_response_status, http_mock))
        response.json.side_effect = self.async_partial(self._get_next_api_response_json, http_mock)
        response.text.side_effect = self.async_partial(self._get_next_api_response_text, http_mock)
        response.__aenter__.return_value = response

        components = params if params else data
        self._sent_http_requests[http_mock].put_nowait((url, headers, components))

        return response

    def configure_http_request_mock(self, http_request_mock):
        http_request_mock.side_effect = functools.partial(self._handle_http_request, http_request_mock)

    def add_http_response(self, http_request_mock, response_status, response_json=None, response_text=None):
        self._response_status_queues[http_request_mock].append(response_status)
        if response_json is not None:
            self._response_json_queues[http_request_mock].put_nowait(response_json)
        if response_text is not None:
            self._response_text_queues[http_request_mock].put_nowait(response_text)

    async def next_sent_request_data(self, http_request_mock):
        return await self._sent_http_requests[http_request_mock].get()

    async def _get_next_websocket_json_message(self, websocket_mock, *args, **kwargs):
        message = await self._incoming_websocket_json_queues[websocket_mock].get()
        if message == self._final_message:
            self._all_ws_delivered.set()
        return message

    async def _get_next_websocket_text_message(self, websocket_mock, *args, **kwargs):
        message = await self._incoming_websocket_text_queues[websocket_mock].get()
        if message == self._final_message:
            self._all_ws_delivered.set()
        return message

    def create_websocket_mock(self):
        ws = AsyncMock()
        ws.send_json.side_effect = lambda sent_message: self._sent_websocket_json_messages[ws].append(sent_message)
        ws.send.side_effect = lambda sent_message: self._sent_websocket_text_messages[ws].append(sent_message)
        ws.receive_json.side_effect = self.async_partial(self._get_next_websocket_json_message, ws)
        ws.recv.side_effect = self.async_partial(self._get_next_websocket_text_message, ws)
        return ws

    def add_websocket_json_message(self, websocket_mock, message):
        self._incoming_websocket_json_queues[websocket_mock].put_nowait(message)

    def add_websocket_text_message(self, websocket_mock, message):
        self._incoming_websocket_text_queues[websocket_mock].put_nowait(message)

    def json_messages_sent_through_websocket(self, websocket_mock):
        return self._sent_websocket_json_messages[websocket_mock]

    def text_messages_sent_through_websocket(self, websocket_mock):
        return self._sent_websocket_text_messages[websocket_mock]

    def run_until_all_text_messages_delivered(self, websocket_mock, timeout: int = 1):
        self._incoming_websocket_text_queues[websocket_mock].put_nowait(self._final_message)
        self._ev_loop.run_until_complete(asyncio.wait_for(self._all_ws_delivered.wait(), timeout))

    def run_until_all_json_messages_delivered(self, websocket_mock, timeout: int = 1):
        self._incoming_websocket_json_queues[websocket_mock].put_nowait(self._final_message)
        self._ev_loop.run_until_complete(asyncio.wait_for(self._all_ws_delivered.wait(), timeout))
