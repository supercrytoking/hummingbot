import asyncio

from collections import deque
from typing import (
    Deque,
    Dict,
    List,
)

from hummingbot.core.api_throttler.data_types import (
    RateLimit,
    RequestPath,
    Seconds,
    TaskLog
)


class APIThrottlerBase:
    def __init__(self,
                 rate_limit_list: List[RateLimit],
                 period_safety_margin: Seconds = 0.1,
                 retry_interval: Seconds = 0.1):
        """
        The APIThrottlerBase is an abstract class meant to describe the functions necessary to handle the
        throttling of API requests through the usage of asynchronous context managers
        """

        # Rate Limit Definitions
        self._rate_limit_list: List[RateLimit] = rate_limit_list

        self._path_rate_limit_map: Dict[RequestPath, RateLimit] = {
            limit.path_url: limit
            for limit in self._rate_limit_list
        }

        # Throttler Parameters
        self._retry_interval: float = retry_interval
        self._period_safety_margin = period_safety_margin

        self._task_logs: Deque[TaskLog] = deque()
        self._pending_task: Deque[int]

        # Event
        self._throttler_stop_event = asyncio.Event()

    def execute_task(self):
        raise NotImplementedError

    def stop(self):
        self._throttler_stop_event.set()
