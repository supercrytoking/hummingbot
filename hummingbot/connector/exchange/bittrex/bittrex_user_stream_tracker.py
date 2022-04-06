import asyncio
import logging
from typing import List, Optional

from hummingbot.connector.exchange.bittrex.bittrex_api_user_stream_data_source import BittrexAPIUserStreamDataSource
from hummingbot.connector.exchange.bittrex.bittrex_auth import BittrexAuth
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class BittrexUserStreamTracker(UserStreamTracker):
    _btust_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._btust_logger is None:
            cls._btust_logger = logging.getLogger(__name__)
        return cls._btust_logger

    def __init__(
            self,
            bittrex_auth: Optional[BittrexAuth] = None,
            trading_pairs: Optional[List[str]] = None,
    ):
        self._bittrex_auth: BittrexAuth = bittrex_auth
        self._trading_pairs: List[str] = trading_pairs or []
        super().__init__(data_source=BittrexAPIUserStreamDataSource(
            bittrex_auth=self._bittrex_auth,
            trading_pairs=self._trading_pairs
        ))

    @property
    def data_source(self) -> UserStreamTrackerDataSource:
        if not self._data_source:
            self._data_source = BittrexAPIUserStreamDataSource(
                bittrex_auth=self._bittrex_auth, trading_pairs=self._trading_pairs)
        return self._data_source

    @property
    def exchange_name(self) -> str:
        return "bittrex"

    async def start(self):
        self._user_stream_tracking_task = safe_ensure_future(
            self.data_source.listen_for_user_stream(self._user_stream)
        )
        await asyncio.gather(self._user_stream_tracking_task)
