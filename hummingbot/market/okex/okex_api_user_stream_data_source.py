#!/usr/bin/env python
import aiohttp
import asyncio

import logging

from typing import (
    Optional,
    AsyncIterable,
    Dict,
    Any,
    List
)

from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.market.okex.okex_auth import OKExAuth

from hummingbot.market.okex.tools import inflate
from hummingbot.market.okex.constants import *

import time


class OKExAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _hausds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._hausds_logger is None:
            cls._hausds_logger = logging.getLogger(__name__)

        return cls._hausds_logger

    def __init__(self, okex_auth: OKExAuth, trading_pairs: Optional[List[str]] = []):
        self._current_listen_key = None
        self._current_endpoint = None
        self._listen_for_user_steam_task = None
        self._last_recv_time: float = 0
        self._auth: OKExAuth = okex_auth
        self._client_session: aiohttp.ClientSession = None
        self._trading_pairs = trading_pairs
        self._websocket_connection: aiohttp.ClientWebSocketResponse = None
        super().__init__()

    @property
    def last_recv_time(self) -> float:
        """Should be updated(using python's time.time()) everytime a message is received from the websocket."""
        return self._last_recv_time

    async def _authenticate_client(self):
        """
        Sends an Authentication request to OKEx's WebSocket API Server
        """

        await self._websocket_connection.send_json(self._auth.generate_ws_auth())

        resp: aiohttp.WSMessage = await self._websocket_connection.receive()
        msg = resp.json()
        if msg["code"] != 200:
            self.logger().error(f"Error occurred authenticating to websocket API server. {msg}")
        
        self.logger().info(f"Successfully authenticated")

    async def _subscribe_topic(self, topic: List[str]):
        subscribe_request = {
            "op": "subscribe",
            "args": topic
        }
        await self._websocket_connection.send_json(subscribe_request)
        resp = await self._websocket_connection.receive()
        msg = resp.json()
        if msg["code"] != 200:
            self.logger().error(f"Error occurred subscribing to topic. {topic}. {msg}")
        self.logger().info(f"Successfully subscribed to {topic}")

    async def get_ws_connection(self) -> aiohttp.client._WSRequestContextManager:
        if self._client_session is None:
            self._client_session = aiohttp.ClientSession()

        stream_url: str = f"{OKCOIN_WS_URI}"
        return self._client_session.ws_connect(stream_url)

    async def _socket_user_stream(self) -> AsyncIterable[str]:
        """
        Main iterator that manages the websocket connection.
        """
        while True:
            raw_msg = await self._websocket_connection.receive()

            if raw_msg.type != aiohttp.WSMsgType.TEXT:
                continue

            message = raw_msg.json()

            yield message

    # TODO needs testing, paper mode is not connecting for some reason
    async def listen_for_user_stream(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        """Subscribe to user stream via web socket, and keep the connection open for incoming messages"""
        while True:
            try:
                # Initialize Websocket Connection
                async with (await self.get_ws_connection()) as ws:
                    self._websocket_connection = ws

                    # Authentication
                    await self._authenticate_client()

                    assets = set()
                    # Subscribe to Topic(s)
                    for trading_pair in self._trading_pairs:
                        # orders
                        await self._subscribe_topic([f"spot/order:{trading_pair}"])
                        # balances
                        source, quote = trading_pair.split('-')
                        assets.add(source)
                        assets.add(quote)
                    
                    # all assets
                    for asset in assets:
                        await self._subscribe_topic([f"spot/account:{asset}"])

                    # Listen to WebSocket Connection
                    async for message in self._socket_user_stream():
                        self._last_recv_time = time.time()

                        # handle all the messages in the queue
                        output.put_nowait(inflate(message))

            except asyncio.CancelledError:
                raise
            except IOError as e:
                self.logger().error(e, exc_info=True)
            except Exception as e:
                self.logger().error(f"Unexpected error occurred! {e} {message}", exc_info=True)
            finally:
                if self._websocket_connection is not None:
                    await self._websocket_connection.close()
                    self._websocket_connection = None
                if self._client_session is not None:
                    await self._client_session.close()
                    self._client_session = None
