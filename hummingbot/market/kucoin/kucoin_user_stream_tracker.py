#!/usr/bin/env python

import asyncio
import logging
from typing import (
    Optional
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.user_stream_tracker import (
    UserStreamTrackerDataSourceType,
    UserStreamTracker
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.kucoin.kucoin_api_user_stream_data_source import KucoinAPIUserStreamDataSource
from hummingbot.market.kucoin.kucoin_auth import KucoinAuth
# from kucoin.client import Client as KucoinClient


class KucoinUserStreamTracker(UserStreamTracker):
    _kust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._kust_logger is None:
            cls._kust_logger = logging.getLogger(__name__)
        return cls._kust_logger

    def __init__(self,
                 data_source_type: UserStreamTrackerDataSourceType = UserStreamTrackerDataSourceType.EXCHANGE_API,
                 kucoin_auth: Optional[KucoinAuth] = None):
        super().__init__(data_source_type=data_source_type)
        self._kucoin_client: KucoinAuth = kucoin_auth
        self._ev_loop: asyncio.events.AbstractEventLoop = asyncio.get_event_loop()
        self._data_source: Optional[UserStreamTrackerDataSource] = None
        self._user_stream_tracking_task: Optional[asyncio.Task] = None

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            if self._data_source_type is UserStreamTrackerDataSourceType.EXCHANGE_API:
                self._data_source = KucoinAPIUserStreamDataSource(kucoin_auth=self._kucoin_client)
            else:
                raise ValueError(f"data_source_type {self._data_source_type} is not supported.")
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "kucoin"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._ev_loop, self._user_stream)
        )
        await safe_gather(self._user_stream_tracking_task)
