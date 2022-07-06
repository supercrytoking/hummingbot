import asyncio
import logging
import time
from typing import List, Optional

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
import hummingbot.connector.exchange.latoken.latoken_stomper as stomper
import hummingbot.connector.exchange.latoken.latoken_web_utils as web_utils
from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class LatokenAPIUserStreamDataSource(UserStreamTrackerDataSource):
    # Recommended to Ping/Update listen key to keep connection alive

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: LatokenAuth,
                 trading_pairs: List[str],
                 domain: str = CONSTANTS.DEFAULT_DOMAIN,
                 api_factory: Optional[WebAssistantsFactory] = None,
                 throttler: Optional[AsyncThrottler] = None,
                 time_synchronizer: Optional[TimeSynchronizer] = None):
        super().__init__()
        self._manage_listen_key_task = None
        self._auth: LatokenAuth = auth
        self._time_synchronizer = time_synchronizer
        self._current_listen_key = None
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)
        self._rest_assistant: Optional[RESTAssistant] = None
        self._ws_assistant: Optional[WSAssistant] = None
        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        return logging.getLogger(__name__) if cls._logger is None else cls._logger

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received message
        :return: the timestamp of the last received message in seconds
        """
        return self._ws_assistant.last_recv_time if self._ws_assistant else 0

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        Connects to the user private channel in the exchange using a websocket connection. With the established
        connection listens to all balance events and order updates provided by the exchange, and stores them in the
        output queue
        """
        while True:
            try:
                self._manage_listen_key_task = safe_ensure_future(self._manage_listen_key_task_loop())
                await self._listen_key_initialized_event.wait()
                if self._ws_assistant is None:
                    self._ws_assistant = await self._api_factory.get_ws_assistant()
                await self._ws_assistant.connect(
                    ws_url=web_utils.ws_url(self._domain),
                    ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
                # connect request
                msg_out = stomper.Frame()
                msg_out.cmd = "CONNECT"
                msg_out.headers.update({
                    "accept-version": "1.1",
                    "heart-beat": "0,0"
                })

                connect_request: WSRequest = WSRequest(payload=msg_out.pack(), is_auth_required=True)
                await self._ws_assistant.send(connect_request)
                await self._ws_assistant.receive()
                # subscription request
                path_params = {'user': self._current_listen_key}

                msg_subscribe_orders = stomper.subscribe(
                    CONSTANTS.ORDERS_STREAM.format(**path_params), CONSTANTS.SUBSCRIPTION_ID_ORDERS, ack="auto")
                msg_subscribe_trades = stomper.subscribe(
                    CONSTANTS.TRADE_UPDATE_STREAM.format(**path_params), CONSTANTS.SUBSCRIPTION_ID_TRADE_UPDATE,
                    ack="auto")
                msg_subscribe_account = stomper.subscribe(
                    CONSTANTS.ACCOUNT_STREAM.format(**path_params), CONSTANTS.SUBSCRIPTION_ID_ACCOUNT, ack="auto")

                _ = await safe_gather(
                    self._ws_assistant.subscribe(request=WSRequest(payload=msg_subscribe_trades)),
                    self._ws_assistant.subscribe(request=WSRequest(payload=msg_subscribe_orders)),
                    self._ws_assistant.subscribe(request=WSRequest(payload=msg_subscribe_account)),
                    return_exceptions=True)
                # queue subscription messages
                async for ws_response in self._ws_assistant.iter_messages():
                    msg_in = stomper.Frame()
                    data = msg_in.unpack(ws_response.data.decode())
                    event_type = int(data['headers']['subscription'].split('_')[0])
                    if event_type == CONSTANTS.SUBSCRIPTION_ID_ACCOUNT or event_type == CONSTANTS.SUBSCRIPTION_ID_ORDERS or event_type == CONSTANTS.SUBSCRIPTION_ID_TRADE_UPDATE:
                        output.put_nowait(data)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Retrying after 5 seconds...")
            finally:
                # Make sure no background task is leaked.
                # client and await client.disconnect()
                self._ws_assistant and await self._ws_assistant.disconnect()
                self._manage_listen_key_task and self._manage_listen_key_task.cancel()
                self._current_listen_key = None
                self._listen_key_initialized_event.clear()
                await self._sleep(5)

    @classmethod
    def _get_throttler_instance(cls) -> AsyncThrottler:
        return AsyncThrottler(CONSTANTS.RATE_LIMITS)

    async def _get_listen_key(self) -> str:
        try:
            data = await web_utils.api_request(
                path=CONSTANTS.USER_ID_PATH_URL,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer,
                domain=self._domain,
                method=RESTMethod.GET,
                is_auth_required=True,
                return_err=False)
        except asyncio.CancelledError:
            raise
        except Exception as exception:
            raise IOError(f"Error fetching user stream listen key. Error: {exception}")

        return data["id"]

    async def _ping_listen_key(self) -> bool:
        try:
            data = await web_utils.api_request(
                path=CONSTANTS.USER_ID_PATH_URL,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer,
                domain=self._domain,
                method=RESTMethod.GET,
                is_auth_required=True,
                return_err=True
            )

            if "id" not in data:
                self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {data}")
                return False

        except asyncio.CancelledError:
            raise
        except Exception as exception:
            self.logger().warning(f"Failed to refresh the listen key {self._current_listen_key}: {exception}")
            return False

        return True

    async def _manage_listen_key_task_loop(self):
        try:
            while True:
                now = int(time.time())
                if self._current_listen_key is None:
                    self._current_listen_key = await self._get_listen_key()
                    self.logger().info(f"Successfully obtained listen key {self._current_listen_key}")
                    self._listen_key_initialized_event.set()
                    self._last_listen_key_ping_ts = int(time.time())

                if now - self._last_listen_key_ping_ts >= CONSTANTS.LISTEN_KEY_KEEP_ALIVE_INTERVAL:
                    success: bool = await self._ping_listen_key()
                    if success:
                        self.logger().info(f"Refreshed listen key {self._current_listen_key}.")
                        self._last_listen_key_ping_ts = int(time.time())
                    else:
                        self.logger().error("Error occurred renewing listen key ...")
                        break
                else:
                    await self._sleep(CONSTANTS.LISTEN_KEY_KEEP_ALIVE_INTERVAL)
        finally:
            self._current_listen_key = None
            self._listen_key_initialized_event.clear()
