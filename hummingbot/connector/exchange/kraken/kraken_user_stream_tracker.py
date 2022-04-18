import logging
from typing import Optional

from hummingbot.connector.exchange.kraken.kraken_api_user_stream_data_source import KrakenAPIUserStreamDataSource
from hummingbot.connector.exchange.kraken.kraken_auth import KrakenAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class KrakenUserStreamTracker(UserStreamTracker):
    _krust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._krust_logger is None:
            cls._krust_logger = logging.getLogger(__name__)
        return cls._krust_logger

    def __init__(self,
                 throttler: AsyncThrottler,
                 kraken_auth: KrakenAuth,
                 api_factory: Optional[WebAssistantsFactory] = None):
        self._throttler = throttler
        self._api_factory = api_factory
        self._kraken_auth: KrakenAuth = kraken_auth
        super().__init__(data_source=KrakenAPIUserStreamDataSource(
            self._throttler,
            self._kraken_auth,
            self._api_factory))

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = KrakenAPIUserStreamDataSource(self._throttler, self._kraken_auth, self._api_factory)
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "kraken"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
