import asyncio
import unittest.mock
from threading import Thread
import websockets
from test.integration.humming_web_app import get_open_port
import json


class HummingWsServerFactory:
    _orig_ws_connect = websockets.connect
    _ws_servers = {}
    host = "127.0.0.1"

    @staticmethod
    def start_new_server(url):
        port = get_open_port()
        ws_server = HummingWsServer(HummingWsServerFactory.host, port)
        HummingWsServerFactory._ws_servers[url] = ws_server
        ws_server.start()
        return ws_server

    @staticmethod
    def reroute_ws_connect(url, **kwargs):
        print(f"reroute {url}")
        if url not in HummingWsServerFactory._ws_servers:
            return HummingWsServerFactory._orig_ws_connect(url, **kwargs)
        ws_server = HummingWsServerFactory._ws_servers[url]
        return HummingWsServerFactory._orig_ws_connect(f"ws://{ws_server.host}:{ws_server.port}", **kwargs)

    @staticmethod
    async def send_str(url, message):
        ws_server = HummingWsServerFactory._ws_servers[url]
        await ws_server.websocket.send(message)

    @staticmethod
    async def send_json(url, data, delay=0):
        await asyncio.sleep(delay)
        ws_server = HummingWsServerFactory._ws_servers[url]
        await ws_server.websocket.send(json.dumps(data))


class HummingWsServer:

    def __init__(self, host, port):
        self._ev_loop: None
        self._started: bool = False
        self.host = host
        self.port = port
        self.websocket = None

    async def _handler(self, websocket, path):
        self.websocket = websocket
        async for msg in self.websocket:
            pass
        print('websocket connection closed')
        return self.websocket

    @property
    def started(self) -> bool:
        return self._started

    def _start(self):
        self._ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ev_loop)
        asyncio.ensure_future(websockets.serve(self._handler, self.host, self.port))
        self._ev_loop.run_forever()

    async def wait_til_started(self):
        while not self._started:
            await asyncio.sleep(0.1)

    async def _stop(self):
        self.port = None
        self._started = False

    def start(self):
        if self.started:
            self.stop()
        thread = Thread(target=self._start)
        thread.daemon = True
        thread.start()

    def stop(self):
        asyncio.ensure_future(self._stop())


class HummingWsServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        cls.ws_server = HummingWsServerFactory.start_new_server("ws://www.google.com/ws/")
        cls._patcher = unittest.mock.patch("websockets.connect", autospec=True)
        cls._mock = cls._patcher.start()
        cls._mock.side_effect = HummingWsServerFactory.reroute_ws_connect

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patcher.stop()

    async def _test_web_socket(self):
        uri = "ws://www.google.com/ws/"
        async with websockets.connect(uri) as websocket:
            await HummingWsServerFactory.send_str(uri, "aaa")
            answer = await websocket.recv()
            print(answer)
            self.assertEqual("aaa", answer)
            await HummingWsServerFactory.send_json(uri, data={"foo": "bar"})
            answer = await websocket.recv()
            print(answer)
            answer = json.loads(answer)
            self.assertEqual(answer["foo"], "bar")
            await self.ws_server.websocket.send("xxx")
            answer = await websocket.recv()
            print(answer)
            self.assertEqual("xxx", answer)

    def test_web_socket(self):
        asyncio.get_event_loop().run_until_complete(self._test_web_socket())


if __name__ == '__main__':
    unittest.main()
