import asyncio
import json
from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor


class NdaxWebSocketAdaptorTests(TestCase):

    def test_sending_messages_increment_message_number(self):
        sent_messages = []
        ws = AsyncMock()
        ws.send.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = NdaxWebSocketAdaptor(websocket=ws)
        payload = {}
        asyncio.get_event_loop().run_until_complete(adaptor.send_request(endpoint_name='TestEndpoint1',
                                                                         payload=payload))
        asyncio.get_event_loop().run_until_complete(adaptor.send_request(endpoint_name='TestEndpoint2',
                                                                         payload=payload))
        asyncio.get_event_loop().run_until_complete(adaptor.send_request(endpoint_name='TestEndpoint3',
                                                                         payload=payload))
        self.assertEqual(3, len(sent_messages))

        message = json.loads(sent_messages[0])
        self.assertEqual(1, message.get('i'))
        message = json.loads(sent_messages[1])
        self.assertEqual(2, message.get('i'))
        message = json.loads(sent_messages[2])
        self.assertEqual(3, message.get('i'))

    def test_request_message_structure(self):
        sent_messages = []
        ws = AsyncMock()
        ws.send.side_effect = lambda sent_message: sent_messages.append(sent_message)

        adaptor = NdaxWebSocketAdaptor(websocket=ws)
        payload = {"TestElement1": "Value1", "TestElement2": "Value2"}
        asyncio.get_event_loop().run_until_complete(adaptor.send_request(endpoint_name='TestEndpoint',
                                                                         payload=payload))

        self.assertEqual(1, len(sent_messages))
        message = json.loads(sent_messages[0])

        self.assertEqual(0, message.get('m'))
        self.assertEqual(1, message.get('i'))
        self.assertEqual('TestEndpoint', message.get('n'))
        message_payload = json.loads(message.get('o'))
        self.assertEqual(payload, message_payload)

    def test_receive_message(self):
        ws = AsyncMock()
        ws.recv.return_value = 'test message'

        adaptor = NdaxWebSocketAdaptor(websocket=ws)
        received_message = asyncio.get_event_loop().run_until_complete(adaptor.recv())

        self.assertEqual('test message', received_message)
