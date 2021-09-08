#!/usr/bin/env python

import asyncio
import aiohttp
import logging
import time
from typing import (
    AsyncIterable,
    Dict,
    Optional
)
import ujson
import websockets

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.kucoin import kucoin_constants as CONSTANTS

KUCOIN_PRIVATE_TOPICS = [
    "/spotMarket/tradeOrders",
    "/account/balance",
]


class KucoinAPIUserStreamDataSource(UserStreamTrackerDataSource):

    PING_TIMEOUT = 50.0

    _kausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._kausds_logger is None:
            cls._kausds_logger = logging.getLogger(__name__)
        return cls._kausds_logger

    def __init__(self, throttler: AsyncThrottler, kucoin_auth: KucoinAuth):
        self._throttler = throttler
        self._current_listen_key = None
        self._current_endpoint = None
        super().__init__()
        self._kucoin_auth: KucoinAuth = kucoin_auth
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def get_listen_key(self):
        async with aiohttp.ClientSession() as client:
            url = CONSTANTS.BASE_PATH_URL + CONSTANTS.PRIVATE_WS_DATA_PATH_URL
            header = self._kucoin_auth.add_auth_to_params("POST", CONSTANTS.PRIVATE_WS_DATA_PATH_URL)
            async with client.post(url, headers=header) as response:  # not rate-limited
                response: aiohttp.ClientResponse = response
                if response.status != 200:
                    raise IOError(f"Error fetching Kucoin user stream listen key. HTTP status is {response.status}.")
                data: Dict[str, str] = await response.json()
                return data

    async def _subscribe_topic(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            for topic in KUCOIN_PRIVATE_TOPICS:
                subscribe_request = {
                    "id": int(time.time()),
                    "type": "subscribe",
                    "topic": topic,
                    "privateChannel": True,
                    "response": True}
                async with self._throttler.execute_task(CONSTANTS.WS_REQUEST_LIMIT_ID):
                    await ws.send(ujson.dumps(subscribe_request))
        except asyncio.CancelledError:
            raise
        except Exception:
            return

    async def get_ws_connection(self) -> websockets.WebSocketClientProtocol:
        stream_url: str = f"{self._current_endpoint}?token={self._current_listen_key}&acceptUserMessage=true"
        self.logger().info(f"Connecting to {stream_url}.")

        async with self._throttler.execute_task(CONSTANTS.WS_CONNECTION_LIMIT_ID):
            return await websockets.connect(stream_url, ping_interval=40, ping_timeout=self.PING_TIMEOUT)

    async def _inner_messages(self, ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        try:
            while True:
                msg: str = await ws.recv()
                self._last_recv_time = time.time()
                yield msg
        finally:
            await ws.close()
            self._current_listen_key = None

    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        ws = None
        while True:
            try:
                if self._current_listen_key is None:
                    creds = await self.get_listen_key()
                    self._current_listen_key = creds["data"]["token"]
                    self._current_endpoint = creds["data"]["instanceServers"][0]["endpoint"]
                    self.logger().debug(f"Obtained listen key {self._current_listen_key}.")

                    ws = await self.get_ws_connection()
                    await self._subscribe_topic(ws)
                    async for msg in self._inner_messages(ws):
                        decoded: Dict[str, any] = ujson.loads(msg)
                        output.put_nowait(decoded)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error while maintaining the user event listen key. Retrying after "
                                    "5 seconds...", exc_info=False)
                self._current_listen_key = None
                if ws is not None:
                    await ws.close()
                await asyncio.sleep(5)
            finally:
                self._current_listen_key = None
                if ws is not None:
                    await ws.close()
