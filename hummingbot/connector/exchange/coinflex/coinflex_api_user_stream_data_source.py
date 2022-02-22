import asyncio
import logging

from typing import (
    Dict,
    List,
    Optional,
)

import hummingbot.connector.exchange.coinflex.coinflex_constants as CONSTANTS
from hummingbot.connector.exchange.coinflex import coinflex_utils
from hummingbot.connector.exchange.coinflex.coinflex_auth import CoinflexAuth
from hummingbot.connector.exchange.coinflex.coinflex_http_utils import build_api_factory
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import (
    WSRequest,
)
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class CoinflexAPIUserStreamDataSource(UserStreamTrackerDataSource):

    HEARTBEAT_TIME_INTERVAL = 30.0

    _bausds_logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: CoinflexAuth,
                 domain: str = "live",
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None):
        super().__init__()
        self._auth: CoinflexAuth = auth
        self._last_recv_time: float = 0
        self._domain = domain
        self._throttler = throttler or self._get_throttler_instance()
        self._api_factory = api_factory or build_api_factory(auth=self._auth)
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._subscribed_channels: List[str] = []

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._bausds_logger is None:
            cls._bausds_logger = logging.getLogger(__name__)
        return cls._bausds_logger

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message
        :return: the timestamp of the last received message in seconds
        """
        if not all(chan in self._subscribed_channels for chan in CONSTANTS.WS_CHANNELS["USER_STREAM"]):
            return 0
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            payload: Dict[str, str] = {
                "op": "subscribe",
                "args": CONSTANTS.WS_CHANNELS["USER_STREAM"],
            }
            subscribe_request: WSRequest = WSRequest(payload=payload)

            await ws.send(subscribe_request)

            self.logger().info("Subscribed to private channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to private streams...",
                exc_info=True
            )
            raise

    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue
        """
        ws = None
        while True:
            try:
                ws: WSAssistant = await self._get_ws_assistant()
                await ws.connect(ws_url=coinflex_utils.websocket_url(domain=self._domain), ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                await ws.send(WSRequest({}, is_auth_required=True))
                await self._subscribe_channels(ws)
                await ws.ping()  # to update last_recv_timestamp

                async for ws_response in ws.iter_messages():
                    data = ws_response.data
                    event_type = data.get("event")
                    if event_type == "subscribe" and data.get("channel"):
                        self._subscribed_channels.append(data.get("channel"))
                    elif len(data) > 0:
                        output.put_nowait(data)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
            finally:
                # Make sure no background task is leaked.
                ws and await ws.disconnect()
                self._subscribed_channels = []
                await self._sleep(5)

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
